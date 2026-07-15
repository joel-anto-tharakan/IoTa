#!/usr/bin/env python3
"""Capture ESP32-CAM images and matching MQTT sensor metadata.

This script is intended to be run periodically, for example every 30 minutes
from a Home Assistant automation or cron-like scheduler.

It uses only Python's standard library:
  - MQTT v3.1.1 is implemented just far enough to subscribe to retained topics.
  - Images are downloaded with urllib.

One-shot example:
  python3 /config/capture_germcam_dataset.py \
    --mqtt-host 10.156.199.155 \
    --node germcam-1 \
    --node germcam-2 \
    --output-dir /media/germcam

Continuous example:
  python3 /config/capture_germcam_dataset.py \
    --node germcam-1 \
    --node germcam-2 \
    --repeat \
    --interval-minutes 30
"""

from __future__ import annotations

import argparse
import json
import os
import random
import select
import socket
import string
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def encode_string(value: str) -> bytes:
    data = value.encode("utf-8")
    return len(data).to_bytes(2, "big") + data


def encode_remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length:
            digit |= 128
        out.append(digit)
        if not length:
            return bytes(out)


def packet(packet_type: int, payload: bytes) -> bytes:
    return bytes([packet_type]) + encode_remaining_length(len(payload)) + payload


def recv_exact(sock: socket.socket, length: int) -> bytes:
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError("MQTT socket closed")
        data += chunk
    return data


def recv_packet(sock: socket.socket, timeout: float) -> tuple[int, bytes] | None:
    readable, _, _ = select.select([sock], [], [], timeout)
    if not readable:
        return None

    first = recv_exact(sock, 1)[0]
    multiplier = 1
    remaining = 0
    while True:
        byte = recv_exact(sock, 1)[0]
        remaining += (byte & 127) * multiplier
        if not byte & 128:
            break
        multiplier *= 128
    return first, recv_exact(sock, remaining)


def parse_publish(first: int, body: bytes) -> tuple[str, bool, bytes]:
    topic_len = int.from_bytes(body[:2], "big")
    topic = body[2 : 2 + topic_len].decode("utf-8", "replace")
    pos = 2 + topic_len
    qos = (first >> 1) & 3
    if qos:
        pos += 2
    return topic, bool(first & 1), body[pos:]


class MinimalMqttClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def __enter__(self) -> "MinimalMqttClient":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        client_id = "dataset-capture-" + "".join(
            random.choice(string.ascii_lowercase) for _ in range(8)
        )
        flags = 0x02
        payload = encode_string(client_id)

        if self.username is not None:
            flags |= 0x80
            payload += encode_string(self.username)
        if self.password is not None:
            flags |= 0x40
            payload += encode_string(self.password)

        variable_header = encode_string("MQTT") + bytes([4, flags]) + b"\x00\x3c"

        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        sock.sendall(packet(0x10, variable_header + payload))

        response = recv_packet(sock, self.timeout)
        if not response or response[0] != 0x20 or len(response[1]) < 2:
            sock.close()
            raise RuntimeError("MQTT broker did not return a valid CONNACK")

        return_code = response[1][1]
        if return_code != 0:
            sock.close()
            raise RuntimeError(f"MQTT connection refused with code {return_code}")

        self.sock = sock

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def subscribe(self, topic: str, packet_id: int = 1) -> None:
        if self.sock is None:
            raise RuntimeError("MQTT client is not connected")
        payload = packet_id.to_bytes(2, "big") + encode_string(topic) + b"\x00"
        self.sock.sendall(packet(0x82, payload))

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = recv_packet(self.sock, max(0.1, deadline - time.monotonic()))
            if response is None:
                continue
            if response[0] >> 4 == 9:
                return
            if response[0] >> 4 == 3:
                continue
        raise TimeoutError(f"Timed out waiting for SUBACK for {topic}")

    def collect(self, seconds: float) -> dict[str, dict[str, Any]]:
        if self.sock is None:
            raise RuntimeError("MQTT client is not connected")

        messages: dict[str, dict[str, Any]] = {}
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            response = recv_packet(self.sock, min(1.0, deadline - time.monotonic()))
            if response is None:
                continue
            first, body = response
            if first >> 4 != 3:
                continue

            topic, retained, payload = parse_publish(first, body)
            text = payload.decode("utf-8", "replace")
            parsed: Any = text
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
            messages[topic] = {
                "topic": topic,
                "retained": retained,
                "payload": text,
                "value": parsed,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        return messages


LED_EFFECTS = {
    0x25: "seven_color_crossfade",
    0x26: "red_fade",
    0x27: "green_fade",
    0x28: "blue_fade",
    0x29: "yellow_fade",
    0x2A: "cyan_fade",
    0x2B: "magenta_fade",
    0x2C: "white_fade",
    0x2D: "seven_color_strobe",
    0x60: "custom",
    0x61: "static",
    0x62: "static_white",
}


def query_magic_home_led(
    ip_addr: str,
    port: int,
    timeout: float,
    name: str,
    mac: str | None,
    model: str | None,
) -> dict[str, Any]:
    """Read LEDnet/Magic Home status directly from the controller.

    The status response is not formally documented by the manufacturer and can
    vary between controller models. We save both parsed fields and the raw bytes
    so future processing can recover anything this parser misses.
    """
    result: dict[str, Any] = {
        "name": name,
        "ip": ip_addr,
        "port": port,
        "mac": mac,
        "model": model,
        "protocol": "magic_home_lednet_tcp_5577",
        "reachable": False,
        "queried_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with socket.create_connection((ip_addr, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(bytes([0x81, 0x8A, 0x8B, 0x96]))
            data = sock.recv(64)
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["reachable"] = True
    result["raw_status_hex"] = data.hex()
    result["raw_status_bytes"] = list(data)
    result["raw_status_length"] = len(data)

    if len(data) >= 3:
        power_code = data[2]
        result["power_code"] = power_code
        if power_code == 0x23:
            result["state"] = "on"
        elif power_code == 0x24:
            result["state"] = "off"
        else:
            result["state"] = None

    if len(data) >= 4:
        effect_code = data[3]
        result["effect_code"] = effect_code
        result["effect"] = LED_EFFECTS.get(effect_code)

    if len(data) >= 6:
        # Common LEDnet controllers report effect speed around this byte.
        result["effect_speed"] = data[5]

    rgb: list[int] | None = None
    if len(data) >= 9:
        rgb = [data[6], data[7], data[8]]
        result["rgb_color"] = rgb

    if len(data) >= 10:
        result["white_level"] = data[9]
        result["warm_white_level"] = data[9]

    brightness_candidates: list[int] = []
    if rgb:
        brightness_candidates.extend(rgb)
    if isinstance(result.get("white_level"), int):
        brightness_candidates.append(result["white_level"])
    if result.get("state") == "off":
        result["brightness"] = 0
    elif brightness_candidates:
        # This is a direct-device brightness estimate. Home Assistant may expose
        # a separate brightness attribute if the integration normalizes state.
        result["brightness"] = max(brightness_candidates)
        result["brightness_source"] = "estimated_from_direct_channels"

    return result


def get_latest_mqtt_snapshot(args: argparse.Namespace, node: str) -> dict[str, Any]:
    base_topic = args.topic_template.format(node=node)
    topic_filter = f"{base_topic}/#"

    with MinimalMqttClient(
        args.mqtt_host,
        args.mqtt_port,
        args.mqtt_user,
        args.mqtt_password,
        args.mqtt_timeout,
    ) as client:
        client.subscribe(topic_filter)
        messages = client.collect(args.mqtt_wait)

    status_msg = messages.get(f"{base_topic}/status", {})
    status = status_msg.get("value") if isinstance(status_msg.get("value"), dict) else {}

    def topic_value(name: str) -> Any:
        msg = messages.get(f"{base_topic}/{name}", {})
        return msg.get("value")

    snapshot = {
        "base_topic": base_topic,
        "status": status,
        "soil_raw": topic_value("soil_raw"),
        "soil_moisture_percent": topic_value("soil_moisture_percent"),
        "jpg_url": topic_value("jpg_url"),
        "stream_url": topic_value("stream_url"),
        "mqtt_messages": messages,
    }

    if isinstance(status, dict):
        snapshot["soil_raw"] = status.get("soil_raw", snapshot["soil_raw"])
        snapshot["soil_moisture_percent"] = status.get(
            "soil_moisture_percent", snapshot["soil_moisture_percent"]
        )
        snapshot["jpg_url"] = status.get("jpg_url", snapshot["jpg_url"])
        snapshot["stream_url"] = status.get("stream_url", snapshot["stream_url"])

    return snapshot


def infer_jpg_url(node: str, snapshot: dict[str, Any], fallback_template: str | None) -> str:
    jpg_url = snapshot.get("jpg_url")
    if isinstance(jpg_url, str) and jpg_url.startswith(("http://", "https://")):
        return jpg_url

    status = snapshot.get("status")
    if isinstance(status, dict):
        ip_addr = status.get("ip")
        if isinstance(ip_addr, str) and ip_addr:
            return f"http://{ip_addr}/jpg"

    if fallback_template:
        return fallback_template.format(node=node)

    raise RuntimeError(f"No JPEG URL found for {node}")


def safe_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H-%M-%S%z")


def download_image(url: str, timeout: float) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "germcam-dataset-capture"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        headers = {key.lower(): value for key, value in response.headers.items()}
        status = getattr(response, "status", None)
        if status and status >= 400:
            raise RuntimeError(f"HTTP {status} while downloading {url}")
        if not data.startswith(b"\xff\xd8"):
            content_type = headers.get("content-type", "")
            raise RuntimeError(
                f"Downloaded data from {url} does not look like JPEG "
                f"(content-type={content_type!r}, bytes={len(data)})"
            )
        return data, headers


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def capture_node(args: argparse.Namespace, node: str, captured_at: datetime) -> dict[str, Any]:
    snapshot = get_latest_mqtt_snapshot(args, node)
    jpg_url = infer_jpg_url(node, snapshot, args.fallback_jpg_url_template)
    image_bytes, http_headers = download_image(jpg_url, args.http_timeout)

    node_dir = Path(args.output_dir) / node
    image_dir = node_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_timestamp(captured_at)}.jpg"
    image_path = image_dir / filename
    image_path.write_bytes(image_bytes)

    metadata_path = node_dir / "metadata.jsonl"
    status = snapshot.get("status") if isinstance(snapshot.get("status"), dict) else {}

    row = {
        "timestamp": captured_at.isoformat(),
        "node": node,
        "base_topic": snapshot["base_topic"],
        "image_path": str(image_path),
        "image_relative_path": str(Path("images") / filename),
        "image_bytes": len(image_bytes),
        "jpg_url": jpg_url,
        "stream_url": snapshot.get("stream_url"),
        "soil_raw": snapshot.get("soil_raw"),
        "soil_moisture_percent": snapshot.get("soil_moisture_percent"),
        "rssi": status.get("rssi"),
        "uptime_ms": status.get("uptime_ms"),
        "free_heap": status.get("free_heap"),
        "camera_ready": status.get("camera_ready"),
        "config_source": status.get("config_source"),
        "soil_enabled": status.get("soil_enabled"),
        "soil_pin": status.get("soil_pin"),
        "dry_raw": status.get("dry_raw"),
        "wet_raw": status.get("wet_raw"),
        "http_content_type": http_headers.get("content-type"),
        "mqtt_status": status,
    }

    if not args.no_led:
        row["led"] = query_magic_home_led(
            args.led_ip,
            args.led_port,
            args.led_timeout,
            args.led_name,
            args.led_mac,
            args.led_model,
        )

    append_jsonl(metadata_path, row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture ESP32-CAM image files with MQTT metadata."
    )
    parser.add_argument("--node", action="append", required=True, help="Node name, e.g. germcam-1")
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("GERMCAM_OUTPUT_DIR", "/media/germcam"),
        help="Dataset root directory.",
    )
    parser.add_argument(
        "--mqtt-host",
        default=os.environ.get("MQTT_HOST", "10.156.199.155"),
        help="MQTT broker host.",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=int(os.environ.get("MQTT_PORT", "1883")),
        help="MQTT broker port.",
    )
    parser.add_argument("--mqtt-user", default=os.environ.get("MQTT_USER"))
    parser.add_argument("--mqtt-password", default=os.environ.get("MQTT_PASSWORD"))
    parser.add_argument(
        "--topic-template",
        default=os.environ.get("GERMCAM_TOPIC_TEMPLATE", "germination/{node}"),
        help="Base MQTT topic template. Use {node} as the placeholder.",
    )
    parser.add_argument(
        "--mqtt-wait",
        type=float,
        default=float(os.environ.get("GERMCAM_MQTT_WAIT", "6")),
        help="Seconds to wait for retained MQTT values after subscribing.",
    )
    parser.add_argument(
        "--mqtt-timeout",
        type=float,
        default=float(os.environ.get("GERMCAM_MQTT_TIMEOUT", "8")),
        help="MQTT socket timeout in seconds.",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=float(os.environ.get("GERMCAM_HTTP_TIMEOUT", "12")),
        help="Image download timeout in seconds.",
    )
    parser.add_argument(
        "--fallback-jpg-url-template",
        default=os.environ.get("GERMCAM_FALLBACK_JPG_URL_TEMPLATE"),
        help="Optional JPEG URL template if MQTT does not provide one.",
    )
    parser.add_argument(
        "--no-led",
        action="store_true",
        help="Do not query the LED strip controller.",
    )
    parser.add_argument(
        "--led-ip",
        default=os.environ.get("LED_IP", "10.156.199.29"),
        help="LED strip controller IP address.",
    )
    parser.add_argument(
        "--led-port",
        type=int,
        default=int(os.environ.get("LED_PORT", "5577")),
        help="LEDnet/Magic Home TCP port.",
    )
    parser.add_argument(
        "--led-timeout",
        type=float,
        default=float(os.environ.get("LED_TIMEOUT", "5")),
        help="LED controller query timeout in seconds.",
    )
    parser.add_argument(
        "--led-name",
        default=os.environ.get("LED_NAME", "led-strip-1"),
        help="LED strip name to store in metadata.",
    )
    parser.add_argument(
        "--led-mac",
        default=os.environ.get("LED_MAC", "E8:CA:50:42:88:51"),
        help="LED strip MAC address to store in metadata.",
    )
    parser.add_argument(
        "--led-model",
        default=os.environ.get("LED_MODEL", "AK001-ZJ21412"),
        help="LED strip model to store in metadata.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed node capture.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success if at least one requested node was captured.",
    )
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="Keep capturing on a fixed interval instead of exiting after one run.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=float(os.environ.get("GERMCAM_INTERVAL_MINUTES", "30")),
        help="Minutes to sleep between repeated capture runs.",
    )
    return parser.parse_args()


def run_capture(args: argparse.Namespace) -> int:
    captured_at = datetime.now().astimezone()
    rows = []
    errors = []

    for node in args.node:
        try:
            row = capture_node(args, node, captured_at)
            rows.append(row)
            print(
                f"captured {node}: {row['image_relative_path']} "
                f"soil={row['soil_moisture_percent']} raw={row['soil_raw']}"
            )
        except Exception as exc:
            errors.append({"node": node, "error": str(exc)})
            print(f"ERROR capturing {node}: {exc}", file=sys.stderr)
            if args.fail_fast:
                break

    print(json.dumps({"captures": rows, "errors": errors}, indent=2))
    if errors and not (args.allow_partial and rows):
        return 1
    return 0


def main() -> int:
    args = parse_args()

    if not args.repeat:
        return run_capture(args)

    sleep_seconds = max(1.0, args.interval_minutes * 60)
    print(
        f"Starting repeated capture every {args.interval_minutes:g} minutes "
        f"for {', '.join(args.node)}"
    )

    try:
        while True:
            run_capture(args)
            next_run = datetime.now().astimezone().timestamp() + sleep_seconds
            print(
                "Next capture after "
                f"{datetime.fromtimestamp(next_run).astimezone().isoformat()}",
                flush=True,
            )
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        print("Stopping repeated capture.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
