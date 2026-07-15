#!/usr/bin/env python
"""
LEDnet LED Strip Controller — raw TCP, no library dependencies.
Connect to LEDnet0033428851 WiFi first, then:

  python led.py on
  python led.py off
  python led.py red
  python led.py "#00FFAA"
  python led.py brightness 75
  python led.py preset 1
  python led.py speed 50
"""

import socket
import sys
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DEVICE_IP = "10.10.123.3"  # fallback for LEDnet AP mode
DEVICE_PORT = 5577
DISCOVERY_PORT = 48899
DISCOVER_MESSAGE = b"HF-A11ASSISTHREAD"

CACHE_FILE = os.path.expanduser("~/.led_device.json")


def _cache_ip(ip):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"ip": ip}, f)
    except:
        pass


def _raw_discover_ip(timeout=3):
    """Discover LEDnet/Magic Home controllers without external packages."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", DISCOVERY_PORT))
    except OSError:
        sock.bind(("", 0))
    sock.settimeout(0.5)

    deadline = time.monotonic() + timeout
    targets = ("<broadcast>", "255.255.255.255")
    try:
        while time.monotonic() < deadline:
            for target in targets:
                try:
                    sock.sendto(DISCOVER_MESSAGE, (target, DISCOVERY_PORT))
                except OSError:
                    pass

            try:
                data, addr = sock.recvfrom(128)
            except socket.timeout:
                continue

            if data == DISCOVER_MESSAGE:
                continue

            decoded = data.decode("ascii", errors="ignore").strip()
            ip = decoded.split(",", 1)[0].strip() if "," in decoded else addr[0]
            if ip:
                _cache_ip(ip)
                return ip
    finally:
        sock.close()

    return None


def _local_ipv4s():
    """Return likely local IPv4 addresses for this computer."""
    ips = set()

    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            ips.add(ip)
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    return sorted(ip for ip in ips if not ip.startswith("127."))


def _subnet_candidates(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return []
    prefix = ".".join(parts[:3])
    return [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" != ip]


def _is_led_port_open(ip, timeout=0.25):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, DEVICE_PORT)) == 0
    finally:
        s.close()


def scan_for_devices():
    """Find controllers on the current network by discovery and TCP scan."""
    found = []

    discovered = _raw_discover_ip(timeout=2)
    if discovered:
        found.append(discovered)

    candidates = []
    for local_ip in _local_ipv4s():
        candidates.extend(_subnet_candidates(local_ip))

    seen = set(found)
    candidates = [ip for ip in candidates if ip not in seen]

    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(_is_led_port_open, ip): ip for ip in candidates}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                if future.result() and ip not in seen:
                    found.append(ip)
                    seen.add(ip)
            except Exception:
                pass

    if found:
        _cache_ip(found[0])

    return found


def _discover_ip():
    """Scan the network for the LED controller."""
    found = _raw_discover_ip()
    if found:
        return found

    try:
        from flux_led import BulbScanner
        scanner = BulbScanner()
        scanner.scan(timeout=3)
        bulbs = scanner.getBulbInfo()
        for b in bulbs:
            ip = b.get("ipaddr") or b.get("ip")
            if ip:
                _cache_ip(ip)
                return ip
    except Exception:
        pass

    found_devices = scan_for_devices()
    if found_devices:
        return found_devices[0]

    return None


def get_device_ip():
    """Get the controller IP — cached, discovered, or fallback."""
    # Try cached first
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f).get("ip")
            if cached:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                if s.connect_ex((cached, DEVICE_PORT)) == 0:
                    s.close()
                    return cached
                s.close()
    except:
        pass
    # Try discovery
    found = _discover_ip()
    if found:
        return found
    # Fallback to default
    return DEVICE_IP

_current_ip = DEVICE_IP  # resolved by main()

# ---------------------------------------------------------------------------
# Protocol helpers — Magic Home / LEDnet binary protocol
# ---------------------------------------------------------------------------

def _send(payload: bytes, timeout=3):
    """Send raw bytes to the device."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((_current_ip, DEVICE_PORT))
        s.send(payload)
    finally:
        s.close()

def _checksum(data: bytearray) -> bytearray:
    data.append(sum(data) & 0xFF)
    return data

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def on():
    _send(_checksum(bytearray([0x71, 0x23, 0x0F])))
    print("ON  💡")

def off():
    _send(_checksum(bytearray([0x71, 0x24, 0x0F])))
    print("OFF  🔌")

def set_rgb(r: int, g: int, b: int):
    """Set RGB color (0-255 each). (0,0,0) turns off."""
    if r == g == b == 0:
        off()
    else:
        _send(_checksum(bytearray([0x31, r, g, b, 0x00, 0xF0, 0x0F])))
        print(f"RGB({r}, {g}, {b})")

def set_warmwhite(level: int):
    """Set warm white 0-255."""
    _send(_checksum(bytearray([0x31, 0x00, 0x00, 0x00, level, 0x0F, 0x0F])))
    print(f"Warm white: {level} ({int(level/2.55)}%)")

def set_preset(code: int):
    """Built-in effect: 0x25-0x2D (presets 1-9)."""
    _send(_checksum(bytearray([code, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0F])))
    print(f"Preset {code - 0x24} started")

def set_speed(speed: int):
    """Effect speed 1-100."""
    _send(_checksum(bytearray([0x0F, speed, 0x00, 0x00, 0x00, 0x00, 0x0F])))
    print(f"Speed: {speed}")

# ---------------------------------------------------------------------------
# Color parsing
# ---------------------------------------------------------------------------

NAMED = {
    "red":      (255,   0,   0),
    "green":    (  0, 255,   0),
    "blue":     (  0,   0, 255),
    "white":    (255, 255, 255),
    "warmwhite":(255, 200, 100),
    "yellow":   (255, 255,   0),
    "cyan":     (  0, 255, 255),
    "magenta":  (255,   0, 255),
    "orange":   (255, 165,   0),
    "purple":   (128,   0, 128),
    "pink":     (255, 192, 203),
    "off":      (  0,   0,   0),
}

def parse_color(s):
    s = s.strip().lower()
    if s in NAMED:
        return NAMED[s]
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 6:
        return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
    return None

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def usage():
    print(__doc__)
    print("Commands: on | off | <color> | <#hex> | brightness <0-100>")
    print("          warmwhite <0-255> | preset <1-9> | speed <1-100>")
    print("          colors | status | scan")

PRESET_NAMES = {
    1: "seven color crossfade", 2: "red fade", 3: "green fade",
    4: "blue fade", 5: "yellow fade", 6: "cyan fade",
    7: "magenta fade", 8: "white fade", 9: "seven color strobe",
}

def main():
    if len(sys.argv) < 2:
        usage()
        return

    cmd = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "scan":
        devices = scan_for_devices()
        if not devices:
            print("No LED controllers found on this network.")
            return
        print("LED controllers found:")
        for ip in devices:
            print(f"  {ip}:{DEVICE_PORT}")
        print(f"Using {devices[0]} for future commands.")
        return

    # Resolve device IP (cached, discovered, or fallback)
    global _current_ip
    _current_ip = get_device_ip()
    ip = _current_ip

    # Test connection first
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((ip, DEVICE_PORT))
        s.close()
    except Exception as e:
        print(f"Cannot reach {ip}:{DEVICE_PORT}")
        print("Are you on the same WiFi as the controller?")
        sys.exit(1)

    # Dispatch
    if cmd == "on":
        on()
    elif cmd == "off":
        off()
    elif cmd in ("colors", "list"):
        print("Colors:")
        for name in sorted(NAMED.keys()):
            r, g, b = NAMED[name]
            print(f"  {name:12s}  #{r:02X}{g:02X}{b:02X}")
        print("  #RRGGBB hex also accepted")

    elif cmd == "status":
        print(f"Device: {_current_ip}:{DEVICE_PORT} — reachable ✓")

    elif cmd == "brightness" or cmd == "dim":
        if not arg:
            print("Usage: python led.py brightness <0-100>")
            return
        pct = max(0, min(100, int(arg)))
        set_warmwhite(int(pct * 255 / 100))

    elif cmd == "warmwhite" or cmd == "ww":
        level = max(0, min(255, int(arg))) if arg else 255
        set_warmwhite(level)

    elif cmd == "preset":
        if not arg:
            print("Presets:")
            for k, v in PRESET_NAMES.items():
                print(f"  {k}: {v}")
            return
        code = int(arg)
        if code < 1 or code > 9:
            print("Preset must be 1-9")
            return
        set_preset(0x25 + code - 1)

    elif cmd == "speed":
        if not arg:
            print("Usage: python led.py speed <1-100>")
            return
        set_speed(max(1, min(100, int(arg))))

    else:
        # Try parsing as a color name or hex
        rgb = parse_color(cmd)
        if rgb:
            if cmd in ("off",):
                off()
            else:
                set_rgb(*rgb)
        else:
            print(f"Unknown: {cmd}")
            usage()

if __name__ == "__main__":
    main()
