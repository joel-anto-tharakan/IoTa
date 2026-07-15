# Arduino and Home Assistant Setup

The Arduino Nano 33 BLE Sense Rev2 connects directly to the Home Assistant
Raspberry Pi over USB. MicroPython reads the onboard sensors every 30 seconds;
a local Home Assistant app converts the serial output to retained MQTT state
and Home Assistant discovery entities.

```text
Nano 33 BLE Sense Rev2 -> USB serial -> Nano USB Sensor Gateway -> MQTT -> Home Assistant
```

## Sensors

| Sensor | Measurements |
| --- | --- |
| HS3003 | Temperature and relative humidity |
| LPS22H | Atmospheric pressure |
| APDS9960 | Clear/red/green/blue channels and estimated illuminance |

The onboard I2C bus uses `SCL=15` and `SDA=14`. No GPIO wiring to the ESP32
devices is required.

## Files

| File | Purpose |
| --- | --- |
| `usb_mqtt/nano_main.py` | Canonical MicroPython firmware |
| `ha_addons/nano_serial_mqtt/nano_main.py` | Firmware copy bundled with the app |
| `ha_addons/nano_serial_mqtt/nano_serial_mqtt.py` | Serial parser, MQTT publisher, and discovery publisher |
| `ha_addons/nano_serial_mqtt/config.yaml` | Home Assistant app definition |
| `ha_addons/nano_serial_mqtt/run.sh` | App entry point and optional firmware installer |
| `ha_addons/nano_serial_mqtt/Dockerfile` | App image |

Keep both copies of `nano_main.py` identical.

## Firmware output

The firmware discards the first pressure reading after startup, then emits a
line like this every 30 seconds:

```text
rH:59.22,T:21.30,Pressure:1031.27,LightClear:21,LightRed:12,LightGreen:6,LightBlue:6,Lux:1.18,LightSaturated:0,LightGain:4,LightIntegrationMs:103.0
```

The APDS9960 uses 4x gain and about 103 ms integration. Illuminance is an
estimate: calibrate `LUX_CALIBRATION_FACTOR` against a reference meter after
final mounting. A channel value at or above 37,800 marks the reading as
saturated.

## MQTT and availability

The gateway publishes retained values to:

```text
germination/nano33-environment/state
germination/nano33-environment/availability
```

Discovery configuration is published below
`homeassistant/sensor/nano33_usb/`. Home Assistant creates an `Arduino Sensor`
device containing temperature, humidity, pressure, illuminance, raw RGBC, and
diagnostic entities.

The gateway publishes `online` when `/dev/ttyACM0` opens and `offline` after a
serial failure. Its MQTT last also publishes `offline`. This prevents stale
measurements from appearing current after the Nano disconnects.

## Deploy the app

Synchronize the bundled firmware, then copy the app to Home Assistant:

```powershell
Copy-Item .\arduino\usb_mqtt\nano_main.py .\arduino\ha_addons\nano_serial_mqtt\nano_main.py
scp .\arduino\ha_addons\nano_serial_mqtt\Dockerfile ha:/addons/nano_serial_mqtt/
scp .\arduino\ha_addons\nano_serial_mqtt\config.yaml ha:/addons/nano_serial_mqtt/
scp .\arduino\ha_addons\nano_serial_mqtt\run.sh ha:/addons/nano_serial_mqtt/
scp .\arduino\ha_addons\nano_serial_mqtt\nano_main.py ha:/addons/nano_serial_mqtt/
scp .\arduino\ha_addons\nano_serial_mqtt\nano_serial_mqtt.py ha:/addons/nano_serial_mqtt/
ssh ha "ha store reload"
ssh ha "ha apps update local_nano_serial_mqtt"
```

The installed app uses `/dev/ttyACM0`, starts automatically, and reconnects
after a Nano reset or cable reconnection.

## Update Nano firmware

In Settings > Apps > Nano USB Sensor Gateway > Configuration, enable
`Install firmware`, restart the app once, and confirm the installation in the
log. Disable the option immediately afterward; it is a one-time maintenance
switch.

## Diagnostics

```powershell
ssh ha "ha apps info local_nano_serial_mqtt"
ssh ha "ha apps logs local_nano_serial_mqtt"
ssh ha "ha apps restart local_nano_serial_mqtt"
```

| Symptom | Check |
| --- | --- |
| No values | Gateway log, USB data cable, and `/dev/ttyACM0` |
| Port busy during firmware update | Stop the gateway before using `mpremote` |
| Source changes do not appear | Rebuild and restart the local app |
| Values remain after unplugging | Confirm the gateway publishes `offline` |
| Illuminance is inaccurate | Calibrate both firmware copies after mounting |
| Light Saturated is on | Reduce gain/integration and update related constants |

The current Paho MQTT callback API warning is cosmetic and does not prevent
publishing.
