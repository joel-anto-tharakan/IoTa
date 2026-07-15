#!/usr/bin/with-contenv bashio

set -e
export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"

exec python3 /app/nano_serial_mqtt.py --serial-port "$(bashio::config 'serial_port')"
