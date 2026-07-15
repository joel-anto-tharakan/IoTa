#!/bin/sh
set -u

SECRETS_FILE="/config/secrets/germcam_capture.env"
if [ ! -r "${SECRETS_FILE}" ]; then
  echo "Missing ${SECRETS_FILE}; capture credentials are not configured." >&2
  exit 1
fi

. "${SECRETS_FILE}"
: "${MQTT_USER:?MQTT_USER is missing from ${SECRETS_FILE}}"
: "${MQTT_PASSWORD:?MQTT_PASSWORD is missing from ${SECRETS_FILE}}"
export MQTT_USER MQTT_PASSWORD

OUTPUT_DIR="/media/germcam"
LOG_FILE="${OUTPUT_DIR}/capture.log"

mkdir -p "${OUTPUT_DIR}"

{
  echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') germcam capture start ==="
  python3 /config/capture_germcam_dataset.py \
    --mqtt-host core-mosquitto \
    --node germcam-1 \
    --node germcam-2 \
    --output-dir "${OUTPUT_DIR}" \
    --allow-partial
  status=$?
  echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') germcam capture exit=${status} ==="
  exit "${status}"
} >> "${LOG_FILE}" 2>&1
