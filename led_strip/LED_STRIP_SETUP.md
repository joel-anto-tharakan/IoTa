# LED Strip Setup

The chamber uses a Magic Home/LEDnet Wi-Fi RGB controller. It is controlled
locally over TCP port 5577; the vendor app and cloud are not required.

```text
Home Assistant -> Magic Home integration -> LED controller -> RGB strip
```

## Confirmed device

| Item | Value |
| --- | --- |
| Home Assistant device | Germination Chamber Light |
| Entity | `light.germination_chamber_germination_chamber_light` |
| Integration | Magic Home (`flux_led`) |
| Address | `10.21.225.29:5577` |
| MAC | `E8:CA:50:42:88:51` |
| Model | `AK001-ZJ21412` |

The address is assigned by DHCP and may change. Reserve it in the router or
hotspot where possible.

## Files

| File | Purpose |
| --- | --- |
| `led.py` | Discovery, reachability checks, and direct light commands |
| `provision_lednet_wifi.py` | Moves the controller from setup mode onto normal Wi-Fi |

## Provision Wi-Fi

In setup mode, the controller exposes an `LEDnet...` access point and normally
uses `10.10.123.3`. Connect the development computer to that network, then run:

```powershell
cd .\led_strip
python .\provision_lednet_wifi.py "YOUR_WIFI_SSID"
```

The script prompts for the Wi-Fi password without displaying it, configures
station mode and DHCP over UDP 48899, then reboots the controller. Wait about
60 seconds for it to join the destination network.

Do not store the real Wi-Fi password in this repository. Passing it with
`--password` can expose it in shell history and is not recommended.

## Direct control

Run these commands from `led_strip` while connected to the same LAN:

```powershell
python .\led.py scan
python .\led.py status
python .\led.py on
python .\led.py off
python .\led.py red
python .\led.py "#00FFAA"
python .\led.py brightness 70
python .\led.py warmwhite 180
python .\led.py preset 1
python .\led.py speed 50
```

`scan` uses LEDnet discovery on UDP 48899 and scans likely local subnets for
TCP 5577. It caches the selected address in:

```text
Windows: %USERPROFILE%\.led_device.json
Linux:   ~/.led_device.json
```

If the controller's address changes, clear that file and scan again.

`brightness` maps a percentage to the controller's warm-white channel. It is
not a measurement of lux, PPFD, or PAR.

## Home Assistant

The controller is already registered with the Magic Home integration. Use
`light.germination_chamber_germination_chamber_light` in dashboards,
automations, and scenes. Inspect its current RGB, brightness, and effect
attributes in Developer Tools > States.

For repeatable germination experiments, record the RGB value, brightness,
photoperiod, strip distance, temperature, humidity, and plant observations.
Prefer static colours to changing or strobing effects.

Example scene:

```yaml
- name: Chamber Seedling White 70
  entities:
    light.germination_chamber_germination_chamber_light:
      state: "on"
      brightness: 180
      rgb_color: [255, 245, 220]
```

This is a repeatable starting point, not a calibrated horticultural
recommendation.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Controller address changed | Clear the cache, run `python .\led.py scan`, and update Home Assistant |
| Setup network remains visible | Reconnect to it and repeat provisioning |
| Home Assistant cannot reach the light | Run `python .\led.py status` and check client-to-client LAN access |
| An attribute is missing | Check Developer Tools > States; support varies by firmware |

`led.py` sends the Magic Home binary protocol directly. Commands end with a
one-byte checksum and support power, RGB, warm white, presets, and effect
speed. The dataset capture script separately queries the controller on port
5577 and stores both parsed and raw light state with each image.
