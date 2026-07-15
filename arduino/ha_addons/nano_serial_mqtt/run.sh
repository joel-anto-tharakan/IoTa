#!/usr/bin/with-contenv bashio

set -e
export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"
SERIAL_PORT="$(bashio::config 'serial_port')"

if bashio::config.true 'install_firmware'; then
    bashio::log.info "Installing bundled Nano firmware on ${SERIAL_PORT}"
    mpremote connect "${SERIAL_PORT}" cp /app/nano_main.py :main.py
    mpremote connect "${SERIAL_PORT}" reset || true
    sleep 2
fi

exec python3 /app/nano_serial_mqtt.py --serial-port "${SERIAL_PORT}"
