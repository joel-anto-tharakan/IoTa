# ESP32 Germcam and Home Assistant Setup

## Scope

This folder is a local copy of the files used by Home Assistant to represent
two ESP32-CAM devices, expose their MQTT camera and soil readings, and save a
dataset sample every 30 minutes.

The live Home Assistant configuration was checked over SSH on 15 July 2026.
The confirmed host is `10.21.225.155`, and `/config` is a symbolic link to
`/homeassistant`.

The ESP32 SD-card configuration is intentionally not included. Use the root
`germcam.example.cfg` as a template and keep the real SD-card config local and
untracked.

## System Flow

```text
ESP32-CAM 1 + soil sensor -- MQTT --> Mosquitto --\
                                                    > capture script
ESP32-CAM 2 + soil sensor -- MQTT --> Mosquitto --/        |
Arduino environment sensors --- MQTT ---------------------/
                                                           v
Magic Home LED at 10.21.225.29 -----------------> /media/germcam
```

The ESP32 devices publish current measurements to MQTT. Home Assistant does
not cause those publications. Its automation runs at minute `00` and `30` of
every hour and starts a one-shot script that collects the ESP32 and Arduino
MQTT values, downloads one image from each available camera, queries the LED
controller, and saves the combined record.

## Confirmed Addresses

| Component | Address |
| --- | --- |
| Home Assistant | `http://homeassistant.local:8123/` |
| Raspberry Pi | `10.21.225.155` |
| MQTT broker for LAN devices | `10.21.225.155:1883` or `homeassistant.local:1883` |
| ESP32-CAM 1 last observed address | `10.21.225.186` |
| LED controller | `10.21.225.29:5577` |
| LED MAC | `E8:CA:50:42:88:51` |
| LED model | `AK001-ZJ21412` |

The Mosquitto add-on address `172.30.33.0` belongs to Home Assistant's
internal container network. It is not the broker address to put in an ESP32
configuration.

## MQTT Topics

Each ESP32 publishes under its own node name:

```text
germination/germcam-1/availability
germination/germcam-1/status
germination/germcam-1/jpg_url
germination/germcam-1/stream_url
germination/germcam-1/soil_raw
germination/germcam-1/soil_moisture_percent
```

ESP32-CAM 2 uses the same suffixes under `germination/germcam-2/`.
ESP32-CAM 1 was previously measured publishing approximately every 30.081
seconds. That is independent of the 30-minute dataset capture schedule.

Useful MQTT checks:

```sh
mosquitto_sub -h homeassistant.local -p 1883 -u MQTT_USER -P MQTT_PASSWORD \
  -t 'germination/germcam-1/#' -v

mosquitto_sub -h homeassistant.local -p 1883 -u MQTT_USER -P MQTT_PASSWORD \
  -t 'germination/+/soil_raw' -v \
  -t 'germination/+/soil_moisture_percent' -v
```

## Confirmed Home Assistant Files

The active files represented by this local bundle are:

```text
/config/
|-- configuration.yaml
|-- automations.yaml
|-- capture_germcam_dataset.py
|-- packages/
|   |-- esp32_camera_1.yaml
|   |-- esp32_camera_2.yaml
|   |-- esp32_soil_sensor_1.yaml
|   |-- esp32_soil_sensor_2.yaml
|   `-- germcam_dataset_capture.yaml
`-- scripts/
    `-- run_germcam_capture.sh
```

The local ESP32 HA package copies live under this folder's `packages` directory.
The dataset Python, shell, and package YAML files are canonical at the project
root and are copied to their respective `/config` locations when deployed.

### `configuration.yaml`

This is Home Assistant's main YAML entry point. Its relevant includes are:

```yaml
homeassistant:
  packages: !include_dir_named packages

automation: !include automations.yaml
script: !include scripts.yaml
scene: !include scenes.yaml
```

Every enabled `.yaml` file in `/config/packages` is loaded automatically.

### `automations.yaml`

This file is loaded by `configuration.yaml` and is currently an empty list:

```yaml
[]
```

The Germcam schedule is not stored here. It is in the package described below.

### Camera and soil packages

| File | Purpose |
| --- | --- |
| `packages/esp32_camera_1.yaml` | Camera 1 availability, RSSI, uptime, heap, JPEG URL and stream URL |
| `packages/esp32_camera_2.yaml` | Camera 2 availability, RSSI, uptime, heap, JPEG URL and stream URL |
| `packages/esp32_soil_1.yaml` | Camera 1 soil raw ADC and moisture percentage |
| `packages/esp32_soil_2.yaml` | Camera 2 soil raw ADC and moisture percentage |

These files define Home Assistant entities. They do not control how often the
ESP32 firmware publishes.

### `packages/germcam_dataset_capture.yaml`

This package defines:

```text
Automation: Germcam dataset capture every 30 minutes
ID:         germcam_dataset_capture_every_30_minutes
Command:    shell_command.capture_germcam_dataset
```

The trigger is:

```yaml
trigger:
  - platform: time_pattern
    minutes: "/30"
```

View it in Home Assistant at:

```text
Settings -> Automations & scenes -> Automations
```

Search for `Germcam dataset capture every 30 minutes`.

### `scripts/run_germcam_capture.sh`

The shell wrapper creates `/media/germcam`, adds timestamps to the capture log,
and runs the Python script once for `germcam-1` and `germcam-2`.

It uses `--allow-partial`, so the automation succeeds when at least one camera
is captured. This is currently important because Germcam 2 has not supplied
the expected JPEG URL during recent tests.

### `capture_germcam_dataset.py`

For each run, the script first reads the retained Arduino environment state
from `germination/nano33-environment/state`. It then performs the following for
each camera node:

1. Subscribes to `germination/<node>/#`.
2. Collects the latest MQTT camera and soil values.
3. Downloads the JPEG URL published by the ESP32.
4. Queries the LED controller directly over TCP port `5577`.
5. Saves the image and appends a JSON Lines metadata record containing the
   matching temperature, humidity, pressure, and illuminance readings.

The LED query is implemented inside this script. No separate LED utility is
needed by the active capture process.

## Saved Dataset

```text
/media/germcam/
|-- capture.log
|-- germcam-1/
|   |-- images/*.jpg
|   `-- metadata.jsonl
`-- germcam-2/
    |-- images/*.jpg
    `-- metadata.jsonl
```

Metadata can include the capture timestamp, image path and size, soil raw
value, moisture percentage, temperature, humidity, air pressure, illuminance,
RSSI, uptime, free heap, camera status, MQTT status objects, and direct LED
state. The LED data can include state,
brightness estimate, RGB colour, effect, effect speed, white level, raw reply,
IP, MAC and model.

## Important Commands

Connect to Home Assistant:

```sh
ssh ha
```

Validate and inspect Home Assistant:

```sh
ha core check
ha core info
ha core logs
ha core restart
```

Inspect Mosquitto:

```sh
ha addons info core_mosquitto
ha addons logs core_mosquitto
ha addons restart core_mosquitto
```

Mosquitto settings are also visible at:

```text
Settings -> Add-ons -> Mosquitto broker -> Configuration
```

Run and inspect a capture manually:

```sh
/bin/sh /config/scripts/run_germcam_capture.sh
tail -n 100 /media/germcam/capture.log
tail -n 1 /media/germcam/germcam-1/metadata.jsonl
find /media/germcam -maxdepth 3 -type f
```

Check Python syntax:

```sh
python3 -m py_compile /config/capture_germcam_dataset.py
```

Copy updated local files back to Home Assistant from this folder:

```powershell
scp ..\capture_germcam_dataset.py ha:/config/
scp ..\config\scripts\run_germcam_capture.sh ha:/config/scripts/
scp .\packages\esp32_camera_1.yaml ha:/config/packages/
scp .\packages\esp32_camera_2.yaml ha:/config/packages/
scp .\packages\esp32_soil_sensor_1.yaml ha:/config/packages/
scp .\packages\esp32_soil_sensor_2.yaml ha:/config/packages/
scp ..\germcam_dataset_capture.yaml ha:/config/packages/
```

Run `ha core check` before restarting Home Assistant after any YAML change.

## Live Configuration Note

The SSH inspection found the current package files on the Pi:

```text
/config/packages/esp32_soil_sensor_1.yaml
/config/packages/esp32_soil_sensor_2.yaml
```

The older `esp32_soil_1.yaml` and `esp32_soil_2.yaml` files are not part of the
current Pi package set. Historical entities from those older definitions still
remain in Home Assistant's entity registry and should be removed through the UI
after checking references; do not edit `.storage` manually.

The Pi also contains `/config/packages/germination_chamber.yaml`, which tracks
seed germination controls. It is unrelated to ESP32 data collection and is not
part of this folder.

## Current Status

- Home Assistant accepted the live configuration during `ha core check`.
- The 30-minute automation and shell command names match the files above.
- The latest capture log showed Germcam 1 succeeding and Germcam 2 missing its
  JPEG URL; the overall run exited successfully because partial captures are
  allowed.
- The dataset remains at `/media/germcam`.
- The real replacement SD-card config is still pending and is not stored here.
