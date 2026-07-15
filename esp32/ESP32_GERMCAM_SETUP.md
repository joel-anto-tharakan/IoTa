# ESP32 Germcam Setup

This folder contains the Home Assistant MQTT packages for two ESP32-CAM nodes,
each with a camera and capacitive soil-moisture sensor.

The ESP32 firmware and real SD-card configuration are not included. Use the
root `germcam.example.cfg` as a credential-free template.

## Data flow

```text
ESP32-CAM nodes -> MQTT telemetry -> Mosquitto -> Home Assistant
       `---- HTTP JPEG/stream URLs ------> Home Assistant cameras
```

The ESP32 devices publish independently. Home Assistant represents their
current state but does not trigger those publications.

## MQTT topics

Node 1 publishes beneath `germination/germcam-1`:

```text
availability
status
jpg_url
stream_url
soil_raw
soil_moisture_percent
```

Node 2 uses `germination/germcam-2`. `status` can include RSSI, uptime, free
heap, camera readiness, IP address, and soil calibration details.

LAN devices should connect to `homeassistant.local:1883` or the Raspberry Pi's
LAN address. Do not use Mosquitto's internal add-on address (`172.30.33.0`) in
an ESP32 configuration.

To inspect all Germcam messages:

```sh
mosquitto_sub -h homeassistant.local -p 1883 -u MQTT_USER -P MQTT_PASSWORD \
  -t 'germination/germcam-1/#' -v
```

## Home Assistant files

| Local file | Home Assistant destination | Purpose |
| --- | --- | --- |
| `packages/esp32_camera_1.yaml` | `/config/packages/` | Camera 1 connectivity, health, and URLs |
| `packages/esp32_camera_2.yaml` | `/config/packages/` | Camera 2 connectivity, health, and URLs |
| `packages/esp32_soil_sensor_1.yaml` | `/config/packages/` | Soil sensor 1 raw and percentage values |
| `packages/esp32_soil_sensor_2.yaml` | `/config/packages/` | Soil sensor 2 raw and percentage values |

Home Assistant loads these packages through:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Each camera and soil sensor uses a distinct device identifier so Home
Assistant displays them as separate devices.

## Deploy

```powershell
scp .\esp32\packages\esp32_camera_1.yaml ha:/config/packages/
scp .\esp32\packages\esp32_camera_2.yaml ha:/config/packages/
scp .\esp32\packages\esp32_soil_sensor_1.yaml ha:/config/packages/
scp .\esp32\packages\esp32_soil_sensor_2.yaml ha:/config/packages/
ssh ha "ha core check"
ssh ha "ha core restart"
```

Do not restart Home Assistant until `ha core check` succeeds.

## Diagnostics

```powershell
ssh ha "ha addons logs core_mosquitto"
ssh ha "ha core logs"
```

At the last documented check, Germcam 1 was publishing successfully. Germcam 2
had not supplied the expected JPEG URL, so its live camera remained pending.

Legacy `esp32_soil_1.yaml` and `esp32_soil_2.yaml` packages are obsolete. If
historical entities remain in the registry, remove them through the Home
Assistant UI after checking references; do not edit `.storage` manually.
