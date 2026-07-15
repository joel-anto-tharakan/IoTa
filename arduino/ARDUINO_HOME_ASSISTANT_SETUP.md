# Arduino and Home Assistant Setup

## Active Setup

The Arduino Nano 33 BLE Sense Rev2 connects directly to the Raspberry Pi by
USB. It runs MicroPython, reads its onboard sensors every 30 seconds, and
prints one serial line. A local Home Assistant app reads the serial port and
publishes the readings through Home Assistant's configured MQTT service.

Home Assistant creates one device named `Arduino Sensor` with these entities:

- `Humidity`
- `Illuminance`
- `Light Blue Raw`
- `Light Clear Raw`
- `Light Green Raw`
- `Light Red Raw`
- `Light Saturated` (diagnostic)
- `Light Gain` (diagnostic)
- `Light Integration Time` (diagnostic)
- `Online`
- `Pressure`
- `Temperature`

```text
Arduino Nano 33 BLE Sense Rev2
  MicroPython main.py
        |
        | USB serial: /dev/ttyACM0
        v
Nano USB Sensor Gateway Home Assistant app
        |
        | MQTT state, availability, and discovery
        v
Home Assistant: Arduino Sensor
```

## Hardware

Use a USB data cable between the Nano and the Raspberry Pi. No GPIO wiring is
needed between the Nano and the ESP32 devices.

The Nano reads its onboard I2C sensors on bus 1 using `SCL=15` and `SDA=14`:

| Sensor | Values | Driver |
| --- | --- | --- |
| HS3003 | Temperature and humidity | `hs3003` |
| LPS22H | Atmospheric pressure | `lps22h` |
| APDS9960 | Ambient light | `apds9960` |

## Active Local Files

| Local path | Purpose |
| --- | --- |
| `usb_mqtt/nano_main.py` | Persistent MicroPython firmware for the Nano. |
| `ha_addons/nano_serial_mqtt/config.yaml` | Home Assistant app metadata, USB access, and MQTT service dependency. |
| `ha_addons/nano_serial_mqtt/Dockerfile` | App image with Python, `pyserial`, and `paho-mqtt`. |
| `ha_addons/nano_serial_mqtt/run.sh` | Starts the gateway with Home Assistant MQTT service details. |
| `ha_addons/nano_serial_mqtt/nano_serial_mqtt.py` | Serial reader, MQTT publisher, and MQTT discovery publisher. |
| `ha_addons/nano_serial_mqtt/nano_main.py` | Firmware copy bundled into the app for installation on the Nano. |
| `../dashboard/germination_chamber.yaml` | Chamber helpers and the live Arduino connectivity template. |
| `../esp32/packages/esp32_camera_1.yaml` | `ESP32 Camera 1` Home Assistant package. |
| `../esp32/packages/esp32_soil_sensor_1.yaml` | `ESP32 Soil Sensor 1` Home Assistant package. |
| `../esp32/packages/esp32_camera_2.yaml` | `ESP32 Camera 2` Home Assistant package. |
| `../esp32/packages/esp32_soil_sensor_2.yaml` | `ESP32 Soil Sensor 2` Home Assistant package. |

## Nano Firmware

Local source: `usb_mqtt/nano_main.py`

Installed board file: `main.py` on the Nano MicroPython filesystem.

The firmware discards the first LPS22H pressure reading after startup, then
prints this format every 30 seconds:

```text
rH:59.22,T:21.30,Pressure:1031.27,LightClear:21,LightRed:12,LightGreen:6,LightBlue:6,Lux:1.18,LightSaturated:0,LightGain:4,LightIntegrationMs:103.0
```

The APDS9960 light configuration is fixed at 4x gain and approximately 103 ms
integration time. The firmware captures all four 16-bit RGBC channels and
calculates estimated illuminance from the RGB channels. It marks a reading as
saturated when any channel reaches 37,800 counts.

`LUX_CALIBRATION_FACTOR` in both firmware copies defaults to `1.0`. The
`Illuminance` entity is therefore an estimate until this multiplier is
calibrated against a reference lux meter with the board in its final mounted
position. Keep these two files synchronized when changing firmware:

```text
usb_mqtt/nano_main.py
ha_addons/nano_serial_mqtt/nano_main.py
```

## Home Assistant App

The local app is named `Nano USB Sensor Gateway`, has the slug
`local_nano_serial_mqtt`, and is currently version `1.1.0`.

Its source is deployed to Home Assistant at:

```text
/addons/nano_serial_mqtt/
```

The app starts automatically after Home Assistant reboots. It opens
`/dev/ttyACM0`, reconnects after a Nano reset or cable reconnection, and logs
each sensor payload.

The app publishes retained MQTT state on:

```text
germination/nano33-environment/state
germination/nano33-environment/availability
```

It publishes MQTT discovery configuration under:

```text
homeassistant/sensor/nano33_usb/<metric>/config
```

The device identifier is `nano33-usb-environment`; the display name is
`Arduino Sensor`.

### USB Availability

The gateway publishes retained `online` and `offline` values to the
availability topic based on the USB serial connection:

- Serial port opens: publish `online`.
- Serial read or open fails: publish `offline`, wait five seconds, and retry.
- Gateway loses its MQTT connection unexpectedly: its MQTT last will publishes
  `offline`.

All MQTT measurement entities subscribe to this topic. When the Nano is
unplugged they become `unavailable`, instead of retaining stale readings. When
the cable is reconnected, the gateway reopens the port, publishes `online`, and
resumes readings.

The superseded native-MQTT chamber variant is no longer part of the local
bundle. The live chamber package uses a short heartbeat based on the Nano
temperature entity and exposes:

```text
binary_sensor.arduino_connected
```

The MQTT discovery sensors remain the source of the Nano measurements.

## ESP32 Device Packages

Home Assistant loads package files through:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

The deployed package files are located at `/config/packages/`. Each package
uses a different `device.identifiers` value so the camera and soil sensor are
shown separately in Home Assistant.

| Home Assistant file | Device name |
| --- | --- |
| `/config/packages/esp32_camera_1.yaml` | `ESP32 Camera 1` |
| `/config/packages/esp32_soil_sensor_1.yaml` | `ESP32 Soil Sensor 1` |
| `/config/packages/esp32_camera_2.yaml` | `ESP32 Camera 2` |
| `/config/packages/esp32_soil_sensor_2.yaml` | `ESP32 Soil Sensor 2` |

The chamber package is deployed at
`/config/packages/germination_chamber.yaml`. Home Assistant apps may expose
the same configuration directory internally as `/homeassistant`.

Assign the devices to the `Germination Chamber` area in Home Assistant to show
them as separate dashboard sections.

## Important Commands

All commands assume that `ha` is the configured SSH target for Home Assistant.

### Connect to Home Assistant

```bash
ssh ha
```

### Update Nano Firmware

The preferred update method uses the firmware copy bundled into gateway
version 1.1.0. In **Settings > Apps > Nano USB Sensor Gateway > Configuration**,
enable `Install firmware`, restart the app once, and confirm this log entry:

```text
Installing bundled Nano firmware on /dev/ttyACM0
```

Immediately disable `Install firmware` afterward. It is a one-time maintenance
switch and should remain off during normal operation.

After modifying the firmware locally, update the bundled copy and deploy the
app source:

```powershell
Copy-Item arduino/usb_mqtt/nano_main.py arduino/ha_addons/nano_serial_mqtt/nano_main.py
```

```bash
scp arduino/ha_addons/nano_serial_mqtt/Dockerfile ha:/addons/nano_serial_mqtt/
scp arduino/ha_addons/nano_serial_mqtt/config.yaml ha:/addons/nano_serial_mqtt/
scp arduino/ha_addons/nano_serial_mqtt/run.sh ha:/addons/nano_serial_mqtt/
scp arduino/ha_addons/nano_serial_mqtt/nano_main.py ha:/addons/nano_serial_mqtt/
scp arduino/ha_addons/nano_serial_mqtt/nano_serial_mqtt.py ha:/addons/nano_serial_mqtt/
ssh ha "ha store reload"
ssh ha "ha apps update local_nano_serial_mqtt"
```

Direct `mpremote` installation remains possible when it is installed in the
terminal. Stop the gateway first so it releases the serial port:

```bash
ssh ha "ha apps stop local_nano_serial_mqtt"
ssh ha "mpremote connect /dev/ttyACM0 cp /config/nano_main.py :main.py"
ssh ha "mpremote connect /dev/ttyACM0 reset"
ssh ha "ha apps start local_nano_serial_mqtt"
```

### Inspect or Restart the Gateway

```bash
ssh ha "ha apps info local_nano_serial_mqtt"
ssh ha "ha apps logs local_nano_serial_mqtt"
ssh ha "ha apps restart local_nano_serial_mqtt"
```

### Update Gateway Source

After changing `ha_addons/nano_serial_mqtt/nano_serial_mqtt.py`:

```bash
scp arduino/ha_addons/nano_serial_mqtt/nano_serial_mqtt.py ha:/addons/nano_serial_mqtt/nano_serial_mqtt.py
ssh ha "ha apps rebuild local_nano_serial_mqtt"
ssh ha "ha apps restart local_nano_serial_mqtt"
```

### Update ESP32 Packages

```bash
scp esp32/packages/esp32_camera_1.yaml ha:/config/packages/
scp esp32/packages/esp32_camera_2.yaml ha:/config/packages/
scp esp32/packages/esp32_soil_sensor_1.yaml ha:/config/packages/
scp esp32/packages/esp32_soil_sensor_2.yaml ha:/config/packages/
ssh ha "ha core check"
ssh ha "ha core restart"
```

### Update the Chamber Package

```bash
scp dashboard/germination_chamber.yaml ha:/config/packages/
ssh ha "ha core check"
ssh ha "ha core restart"
```

### Verify Arduino Availability

Check the gateway and the registered MQTT entity:

```bash
ssh ha "ha apps logs local_nano_serial_mqtt"
ssh ha "grep -n 'germination_chamber_arduino_connected' /config/.storage/core.entity_registry"
```

With Home Assistant running, unplugging the Nano should set the connectivity
indicator to off and all MQTT measurements to `unavailable`. Reconnecting it
should restore them.

## Troubleshooting

| Symptom | Command |
| --- | --- |
| No Arduino values | `ssh ha "ha apps logs local_nano_serial_mqtt"` |
| Port busy while updating firmware | Stop `local_nano_serial_mqtt` before using `mpremote`. |
| Gateway source change does not appear | Rebuild and restart the local app. |
| ESP32 values are grouped together | Check that each package has its own `device.identifiers`. |
| Measurements retain stale values after unplugging | Confirm the gateway logs a serial error and publishes `offline`; rebuild it if the local source was changed. |
| Gateway cannot start while Nano is unplugged | Plug in the Nano first. The app configuration requires `serial_port` to reference a currently present TTY device. |
| Illuminance is inaccurate | Mount the board permanently, compare it with a reference meter, and adjust `LUX_CALIBRATION_FACTOR` in both firmware copies. |
| `Light Saturated` is on | Reduce APDS9960 gain or integration time and update the matching metadata and saturation threshold. |

The gateway currently emits a Paho MQTT callback API v1 deprecation warning.
This warning is cosmetic and does not prevent publishing.
