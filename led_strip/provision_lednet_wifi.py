#!/usr/bin/env python
"""
Provision a LEDnet/Magic Home style LED controller onto another Wi-Fi network.

Connect this computer to the LEDnet access point first, then run:

  python provision_lednet_wifi.py "peepee poopoo"

The script prompts for the Wi-Fi password and tries the common LEDnet
Hi-Flying/Zengge AT command path on UDP port 48899.
"""

from __future__ import annotations

import argparse
import getpass
import socket
import sys
import time
from dataclasses import dataclass


DISCOVERY_PORT = 48899
DISCOVER_MESSAGE = b"HF-A11ASSISTHREAD"
DEFAULT_TARGETS = ("10.10.123.3", "10.10.100.254", "192.168.4.1")


@dataclass
class CommandResult:
    target: str
    command: str
    response: str | None

    @property
    def ok(self) -> bool:
        return self.response is not None and self.response.startswith("+ok")


def create_udp_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", DISCOVERY_PORT))
    except OSError:
        sock.bind(("", 0))
    sock.settimeout(1.0)
    return sock


def send_udp(sock: socket.socket, target: str, message: bytes, timeout: float = 1.5) -> str | None:
    sock.settimeout(timeout)
    sock.sendto(message, (target, DISCOVERY_PORT))
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            data, _addr = sock.recvfrom(256)
        except socket.timeout:
            return None

        if data == message:
            continue
        return data.decode("ascii", errors="replace").strip()

    return None


def discover_targets(sock: socket.socket) -> list[str]:
    targets = list(DEFAULT_TARGETS)

    for target in ("255.255.255.255", "<broadcast>", *DEFAULT_TARGETS):
        try:
            response = send_udp(sock, target, DISCOVER_MESSAGE, timeout=0.8)
        except OSError:
            continue

        if not response or "," not in response:
            continue

        ip = response.split(",", 1)[0].strip()
        if ip and ip not in targets:
            targets.insert(0, ip)

    return targets


def probe(sock: socket.socket, targets: list[str]) -> str | None:
    print("Looking for the LED controller on the LEDnet setup network...")

    for target in targets:
        for message in (DISCOVER_MESSAGE, b"AT+LVER\r"):
            try:
                response = send_udp(sock, target, message)
            except OSError:
                continue

            if response:
                print(f"Found response from {target}: {response}")
                if response.startswith("+ok") or "," in response:
                    return target

    print("No setup response received on UDP 48899.")
    return None


def send_command(sock: socket.socket, target: str, command: str) -> CommandResult:
    response = send_udp(sock, target, command.encode("ascii") + b"\r", timeout=2.0)
    result = CommandResult(target=target, command=command, response=response)
    display_command = command
    if command.startswith("AT+WSKEY="):
        parts = command.split(",", maxsplit=2)
        if len(parts) == 3:
            display_command = f"{parts[0]},{parts[1]},********"
    if response:
        print(f"{display_command} -> {response}")
    else:
        print(f"{display_command} -> no response")
    time.sleep(0.4)
    return result


def provision(target: str, ssid: str, password: str, force_reboot: bool) -> bool:
    sock = create_udp_socket()

    commands = [
        "AT+WMODE=STA",
        "AT+WANN=DHCP,0.0.0.0,0.0.0.0,0.0.0.0",
        f"AT+WSSSID={ssid}",
        f"AT+WSKEY=WPA2PSK,AES,{password}",
    ]

    print(f"Sending Wi-Fi settings to {target}...")
    results = [send_command(sock, target, command) for command in commands]

    ok_count = sum(result.ok for result in results)
    if ok_count < 2 and not force_reboot:
        print()
        print("The controller did not acknowledge enough setup commands.")
        print("I did not reboot it. Check you are connected to LEDnet and try again.")
        print("If it was responding but not with +ok, rerun with --force-reboot.")
        return False

    print("Rebooting the LED controller so it can join the new Wi-Fi...")
    reboot = send_command(sock, target, "AT+Z")
    return ok_count >= 2 or reboot.ok or force_reboot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect a LEDnet LED strip controller to another Wi-Fi network.",
    )
    parser.add_argument("ssid", help="Wi-Fi/hotspot name for the LED strip to join")
    parser.add_argument("--password", help="Wi-Fi password. Omit to be prompted.")
    parser.add_argument(
        "--target",
        help="LED controller setup IP. Defaults to auto-detect, then 10.10.123.3.",
    )
    parser.add_argument(
        "--force-reboot",
        action="store_true",
        help="Reboot even if setup commands are not acknowledged.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password
    if password is None:
        password = getpass.getpass(f"Password for {args.ssid}: ")

    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 2

    sock = create_udp_socket()
    targets = [args.target] if args.target else discover_targets(sock)
    target = args.target or probe(sock, targets) or "10.10.123.3"
    sock.close()

    print()
    print("Before continuing, make sure this computer is connected to LEDnet0033428851.")
    confirm = input(f"Send {args.ssid!r} credentials to {target}? [y/N] ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Cancelled.")
        return 1

    if provision(target, args.ssid, password, args.force_reboot):
        print()
        print("Done. Wait about 60 seconds, then check the iPhone hotspot client list.")
        print("If LEDnet0033428851 disappears, the strip probably joined the hotspot.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
