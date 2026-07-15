# Germination Chamber Home Assistant Dashboard

## Overview

This folder contains the Home Assistant configuration created for the mini germination chamber. The chamber has a physical 4-by-6 seed tray, giving 24 independently tracked seed positions.

The completed dashboard provides:

- A clickable 4-by-6 representation of the seed tray.
- Manual germination state tracking for all 24 positions.
- Total germinated seed count and germination percentage.
- Temperature, humidity, pressure, and soil-moisture readings.
- Grow-light control with brightness adjustment.
- Camera and sensor connectivity indicators.
- A chamber camera image.
- Historical graphs for environmental conditions and germination progress.

Only standard Home Assistant cards are used. No HACS dashboard cards or custom frontend components are required.

## Local file inventory

| Local file | Purpose | Home Assistant destination |
| --- | --- | --- |
| `germination_chamber.yaml` | Defines the 24 seed helpers, germination count, and connectivity sensors. | `/config/packages/germination_chamber.yaml` |
| `chamber_dashboard.yaml` | Complete Lovelace raw dashboard configuration. | Paste into the Chamber dashboard Raw configuration editor. |
| `vision_germination_automation_example.yaml` | Suggested MQTT contract and automation for future vision-based detection. | Reference implementation; adapt when the vision service exists. |
| `configuration-packages-snippet.yaml` | Shows the package-loader block required in `configuration.yaml`. | Merge into `/config/configuration.yaml` only when package loading is missing. |
| `GERMINATION_CHAMBER_DASHBOARD.md` | Dashboard-specific technical handover, deployment instructions, commands, and troubleshooting. | Documentation only. |

## Home Assistant system inspected

The target system was inspected through the local SSH alias `ha`.

- Home Assistant OS: 18.1
- Home Assistant Core at the time of implementation: 2026.7.1
- Main configuration directory: `/config`
- Chamber dashboard storage record: `/config/.storage/lovelace.dashboard_chamber`
- Package loader: already enabled in `/config/configuration.yaml`

Do not manually edit files inside `/config/.storage`. The Chamber dashboard is storage-managed, so its YAML should be updated through the Home Assistant Raw configuration editor.

## Final verified remote layout

The following active package files were confirmed in `/config/packages` after cleanup:

| Remote file | Purpose |
| --- | --- |
| `/config/packages/esp32_camera_1.yaml` | Camera 1 MQTT entities. |
| `/config/packages/esp32_camera_2.yaml` | Camera 2 MQTT entities. |
| `/config/packages/esp32_soil_sensor_1.yaml` | Soil sensor 1 connectivity and moisture entities. |
| `/config/packages/esp32_soil_sensor_2.yaml` | Soil sensor 2 connectivity and moisture entities. |
| `/config/packages/germcam_dataset_capture.yaml` | Periodic germination-camera dataset capture automation. |
| `/config/packages/germination_chamber.yaml` | Seed-state helpers and germination summary sensors. |

The Chamber dashboard was confirmed at `/config/.storage/lovelace.dashboard_chamber` with title `Chamber`, path `chamber`, and layout type `panel`.

### Cleanup performed

The following obsolete files were removed after confirming that no dashboard, automation, script, or scene referenced their legacy entity IDs:

- `/config/packages/esp32_soil_1.yaml`
- `/config/packages/esp32_soil_2.yaml`
- `/config/packages/germcam_mqtt.yaml.disabled`

The first two files duplicated the MQTT topics already represented by the newer `esp32_soil_sensor_1.yaml` and `esp32_soil_sensor_2.yaml` packages. The third file was a disabled superseded aggregate MQTT package. Home Assistant configuration validation succeeded and Core was restarted after this cleanup.

## Changes implemented

### 1. Created 24 persistent seed-state helpers

The file `germination_chamber.yaml` defines one `input_boolean` for every physical seed slot:

- Rows: A, B, C, and D.
- Columns: 1 through 6.
- Entity range: `input_boolean.seed_a1` through `input_boolean.seed_d6`.

An off helper represents a seed that has not germinated. An on helper represents a germinated seed. Home Assistant restores helper state across normal restarts because no forced `initial` value is configured.

The dashboard tiles are read-only: both card and icon tap actions are set to `none`. Every position keeps the `mdi:seed-outline` icon; it is neutral while off and green while on. A future vision automation, rather than a dashboard user, will turn the helpers on.

### 2. Added germination and connectivity templates

The package defines these template entities:

| Entity | Function |
| --- | --- |
| `sensor.germinated_seeds` | Counts how many of the 24 seed helpers are on. |
| `binary_sensor.arduino_connected` | Reports connected when Arduino temperature data was received in the previous three minutes. |
| `binary_sensor.led_strip_connected` | Reports connected while the LED-strip light entity is available. |

The germinated-seed count uses `state_class: measurement`, allowing Home Assistant Recorder to retain its history for the progress graph. The previous success-rate gauge and percentage sensor were removed.

### 3. Added a full-width dashboard layout

The original empty Sections dashboard was replaced with a native Panel view containing one vertical stack. This avoids the narrow nested cards produced by the original Sections layout.

The final layout contains:

1. A six-card summary row with ambient light and no success-rate gauge.
2. A two-column operational area containing the seed tray and chamber controls.
3. Two live-camera cards.
4. A four-chart trends row.

The configuration remains responsive because the major areas use Home Assistant Grid cards.

### 4. Added live chamber measurements

The dashboard uses the following entities discovered from the Home Assistant entity registry:

| Measurement | Entity ID |
| --- | --- |
| Temperature | `sensor.nano_33_environment_sensor_nano_temperature` |
| Humidity | `sensor.nano_33_environment_sensor_nano_humidity` |
| Pressure | `sensor.nano_33_environment_sensor_nano_pressure` |
| Ambient light | `sensor.nano_33_environment_sensor_nano_ambient_light` |
| Soil moisture, sensor 1 | `sensor.germcam_1_soil_moisture_2` |
| Raw soil moisture, sensor 1 | `sensor.germcam_1_soil_raw_moisture_2` |

Temperature, humidity, pressure, and soil moisture are presented in the summary area. The trends section retains 72 hours of visible environmental history.

### 5. Added chamber controls and equipment status

| Function | Entity ID |
| --- | --- |
| Grow light | `light.germination_chamber_germination_chamber_light` |
| Soil sensor 1 online status | `binary_sensor.germcam_1_soil_sensor_germcam_1_soil_sensor_online` |
| Soil sensor 2 online status | `binary_sensor.esp32_soil_sensor_2_esp32_soil_sensor_2_online` |
| Camera 1 online status | `binary_sensor.germcam_1_camera_germcam_1_camera_online` |
| Camera 2 online status | `binary_sensor.esp32_camera_2_esp32_camera_2_online` |
| Arduino connectivity | `binary_sensor.arduino_connected` |
| LED-strip connectivity | `binary_sensor.led_strip_connected` |
| Camera 1 snapshot | `camera.germcam_1_live` |
| Camera 2 live stream | `camera.germcam_2_live` |

The grow-light tile is compact and does not include the large inline brightness slider. The six status tiles show both cameras, both soil sensors, the Arduino, and the LED strip as connected or disconnected.

The intended Camera 1 Generic Camera entity is `camera.germcam_1_live`. It is
currently configured as a snapshot-only camera:

- Still image: `{{ states('sensor.germcam_1_camera_jpeg_url') }}`
- Stream source: not configured
- Frame rate: `0.2 FPS` (one image refresh every five seconds)

The URL template follows address changes reported by the ESP32 over MQTT. If
the JPEG URL sensor becomes unavailable, Generic Camera temporarily retains
its last successfully fetched image. The MQTT URL sensors also remain
available for telemetry and dataset capture. The live Home Assistant registry
contains the Generic Camera entity, and the dashboard card references it as
`camera.germcam_1_live`. Camera 2 remains a placeholder until the second
ESP32-CAM is connected. When it is available, create a separate Generic Camera
using:

- Still image: `{{ states('sensor.esp32_camera_2_esp32_camera_2_jpeg_url') }}`
- Stream source: `{{ states('sensor.esp32_camera_2_esp32_camera_2_stream_url') }}`

### 6. Added historical graphs

The dashboard includes:

- Temperature over the previous 72 hours.
- Humidity and soil moisture over the previous 72 hours.
- Air pressure over the previous 72 hours.
- Germinated seed count over the previous 168 hours (seven days).

Historical data depends on Home Assistant Recorder. Newly added entities will accumulate graph data after they begin reporting.

## Deployment

### Package file

The target installation already contains this package loader in `/config/configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Therefore, only the package file needs to be copied:

```powershell
scp .\dashboard\germination_chamber.yaml ha:/config/packages/germination_chamber.yaml
```

Check the complete Home Assistant configuration before restarting:

```powershell
ssh ha "ha core check"
```

When the check reports `Command completed successfully`, restart Home Assistant Core:

```powershell
ssh ha "ha core restart"
```

### Dashboard configuration

The Chamber dashboard is managed in storage mode. Deploy `chamber_dashboard.yaml` as follows:

1. Open Home Assistant.
2. Open the **Chamber** dashboard.
3. Select the pencil icon to edit the dashboard.
4. Open the three-dot menu.
5. Select **Raw configuration editor**.
6. Replace the complete existing configuration with the contents of `chamber_dashboard.yaml`.
7. Save the dashboard.

No Home Assistant restart is required after saving Lovelace raw configuration.

## Important commands

### Connect to Home Assistant

```powershell
ssh ha
```

### Validate the configuration

```powershell
ssh ha "ha core check"
```

### Restart Home Assistant Core

```powershell
ssh ha "ha core restart"
```

### Upload the package

```powershell
scp .\dashboard\germination_chamber.yaml ha:/config/packages/germination_chamber.yaml
```

### Download a backup copy of the deployed package

```powershell
scp ha:/config/packages/germination_chamber.yaml .\dashboard\germination_chamber.remote-backup.yaml
```

### Verify that the package exists remotely

```powershell
ssh ha "ls -l /config/packages/germination_chamber.yaml"
```

### Inspect relevant entity IDs

```powershell
ssh ha "jq -r '.data.entities[] | [.entity_id, .original_name, .platform] | @tsv' /config/.storage/core.entity_registry | grep -Ei 'nano|germcam|soil|camera|germination'"
```

This last command is read-only. It queries the entity registry and is useful if an integration recreates an entity under a different ID.

## Normal operation

1. Open the Chamber dashboard.
2. Inspect the temperature, humidity, pressure, and soil-moisture summary.
3. Confirm that seed positions cannot be changed from the dashboard.
4. Confirm that a seed icon turns green when its helper is turned on by automation.
5. Confirm that the germinated count increases.
6. Use the compact grow-light tile to control the chamber light.
7. Review the equipment connectivity tiles, live cameras, and trend graphs.

Long-term seed state remains latched until the helpers are deliberately reset for a new germination batch.

## Troubleshooting

### A sensor card has no value

Open **Developer Tools → States** and search for the entity ID. If its state is `unavailable`, the dashboard configuration is valid but the source device is not currently publishing data. Check the Arduino/ESP32 power, Wi-Fi connection, MQTT broker connection, and MQTT discovery topics.

### The dashboard reports an entity does not exist

Confirm that Home Assistant was restarted after installing the package. Then search **Developer Tools → States** for `seed_a1`, `germinated_seeds`, `arduino_connected`, or `led_strip_connected`.

Run another configuration check if necessary:

```powershell
ssh ha "ha core check"
```

### Seed states disappeared

The helpers normally restore their previous states. Check whether the package was renamed, removed, or loaded with different entity keys. Adding an `initial` value would reset states on every Home Assistant startup and should be avoided for this use case.

### Graphs are empty

Graphs need historical Recorder data. Confirm that the source entity has a valid numeric state and allow time for readings to accumulate. The germination graph changes only when seed positions are toggled.

### Dashboard layout is narrow

Confirm that `chamber_dashboard.yaml` uses `type: panel` at the view level. The earlier `type: sections` version constrained nested grids and produced narrow gauges and graph cards on desktop displays.

### Configuration validation fails

Do not restart until `ha core check` succeeds. Review YAML indentation and confirm that `/config/configuration.yaml` contains only one `homeassistant:` key. If it already has a `homeassistant:` section, merge `packages: !include_dir_named packages` into that existing section rather than creating another one.

## Safety and maintenance notes

- Run `ha core check` before every YAML-driven restart.
- Do not manually edit `/config/.storage/lovelace.dashboard_chamber`.
- Keep entity IDs stable when renaming display names in Home Assistant.
- Back up `/config/packages/germination_chamber.yaml` before structural changes.
- Keep the seed tiles read-only. Vision automation should call `input_boolean.turn_on` and should never automatically turn a germinated seed off.
- Reset all seed helpers only when beginning a new germination batch.
