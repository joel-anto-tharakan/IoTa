# Germination Chamber Dashboard

This folder contains the Home Assistant package and dashboard for a 4 x 6
germination tray. It uses standard Home Assistant cards and requires no HACS
frontend components.

## Files

| File | Purpose |
| --- | --- |
| `germination_chamber.yaml` | Seed helpers, germination count, and connectivity templates |
| `chamber_dashboard.yaml` | Complete Lovelace dashboard configuration |
| `vision_germination_automation_example.yaml` | Reference contract for future vision detections |
| `configuration-packages-snippet.yaml` | Package-loader example |

## Dashboard contents

The full-width Panel view provides:

- temperature, humidity, pressure, illuminance, soil moisture, and germinated
  count;
- a 4 x 6 seed tray;
- grow-light control;
- connectivity for two cameras, two soil sensors, the Arduino, and LED strip;
- two camera panels; and
- environment and germination history graphs.

The dashboard references entity IDs confirmed in the live Home Assistant
registry. If an integration is recreated, check Developer Tools > States for
new suffixed IDs.

## Seed state

`germination_chamber.yaml` creates `input_boolean.seed_a1` through
`input_boolean.seed_d6`. Their states persist across normal restarts because
no forced `initial` value is configured.

`sensor.germinated_seeds` counts the enabled helpers. The dashboard tiles are
read-only: automation should turn a helper on after germination is confirmed
and should never turn it off automatically. Reset all helpers only when a new
batch begins.

The package also defines:

| Entity | Meaning |
| --- | --- |
| `binary_sensor.arduino_connected` | A temperature reading arrived within three minutes |
| `binary_sensor.led_strip_connected` | The Home Assistant light entity is available |

## Cameras

Camera 1 uses the UI-created Generic Camera entity `camera.germcam_1_live`,
with its still-image URL supplied by the MQTT JPEG URL sensor. Camera 2 is a
placeholder until the second ESP32-CAM and its Generic Camera entity are
available.

## Deploy the package

Home Assistant must contain:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Copy and validate the package:

```powershell
scp .\dashboard\germination_chamber.yaml ha:/config/packages/germination_chamber.yaml
ssh ha "ha core check"
ssh ha "ha core restart"
```

Do not restart if validation fails.

## Install the dashboard

The Chamber dashboard is storage-managed:

1. Open the Chamber dashboard and enter edit mode.
2. Open the three-dot menu and select Raw configuration editor.
3. Replace the configuration with `chamber_dashboard.yaml`.
4. Save.

Do not edit `/config/.storage/lovelace.dashboard_chamber` directly. Dashboard
changes do not require a Core restart.

## Future vision automation

`vision_germination_automation_example.yaml` is not active. It proposes MQTT
messages such as:

```json
{"slot":"A1","germinated":true,"confidence":0.94,"observations":5}
```

The example accepts only A1-D6, a positive result, confidence of at least
0.90, and at least three consistent observations before latching the helper
on. A production vision publisher still needs to be implemented and tested.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing entity | Restart after installing the package, then use Developer Tools > States |
| Empty graph | Confirm Recorder is enabled and allow readings to accumulate |
| Seed states disappeared | Check that helper keys were not renamed and no `initial` value was added |
| Narrow dashboard | Confirm the view uses `type: panel` |
| Camera retains an old image | Check the MQTT JPEG URL and ESP32 availability |
| YAML validation fails | Check indentation and avoid a duplicate `homeassistant:` key |

Keep entity IDs stable, validate YAML before restarts, and back up the package
before structural changes.
