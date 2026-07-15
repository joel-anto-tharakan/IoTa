#!/usr/bin/env python3
"""Persistent Nano USB serial to MQTT gateway for Home Assistant."""

import argparse
import json
import logging
import os
import time

import paho.mqtt.client as mqtt
import serial

MQTT_STATE_TOPIC = "germination/nano33-environment/state"
MQTT_AVAILABILITY_TOPIC = "germination/nano33-environment/availability"
MQTT_CLIENT_ID = "nano33-usb-mqtt-gateway"
DISCOVERY_PREFIX = "homeassistant"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("nano-serial-mqtt")


def parse_reading(line: str) -> dict:
    fields = dict(item.split(":", 1) for item in line.strip().split(","))
    return {
        "temperature": float(fields["T"]),
        "humidity": float(fields["rH"]),
        "pressure": float(fields["Pressure"]),
        "light_clear": int(fields["LightClear"]),
        "light_red": int(fields["LightRed"]),
        "light_green": int(fields["LightGreen"]),
        "light_blue": int(fields["LightBlue"]),
        "illuminance": float(fields["Lux"]),
        "light_saturated": fields["LightSaturated"] == "1",
        "light_gain": int(fields["LightGain"]),
        "light_integration_ms": float(fields["LightIntegrationMs"]),
    }


def publish_discovery(client: mqtt.Client) -> None:
    device = {
        "identifiers": ["nano33-usb-environment"],
        "name": "Arduino Sensor",
        "manufacturer": "Arduino",
        "model": "Nano 33 BLE Sense Rev2",
    }
    sensors = {
        "temperature": {
            "name": "Temperature",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
        "humidity": {
            "name": "Humidity",
            "unit_of_measurement": "%",
            "device_class": "humidity",
        },
        "pressure": {
            "name": "Pressure",
            "unit_of_measurement": "hPa",
            "device_class": "atmospheric_pressure",
        },
        "illuminance": {
            "name": "Illuminance",
            "unit_of_measurement": "lx",
            "device_class": "illuminance",
        },
        "light": {
            "name": "Light Clear Raw",
            "value_key": "light_clear",
            "icon": "mdi:brightness-6",
        },
        "light_red": {"name": "Light Red Raw", "icon": "mdi:palette"},
        "light_green": {"name": "Light Green Raw", "icon": "mdi:palette"},
        "light_blue": {"name": "Light Blue Raw", "icon": "mdi:palette"},
        "light_gain": {
            "name": "Light Gain",
            "icon": "mdi:amplifier",
            "entity_category": "diagnostic",
        },
        "light_integration_ms": {
            "name": "Light Integration Time",
            "unit_of_measurement": "ms",
            "icon": "mdi:timer-outline",
            "entity_category": "diagnostic",
        },
    }

    for metric, details in sensors.items():
        details = details.copy()
        value_key = details.pop("value_key", metric)
        config = {
            **details,
            "unique_id": f"nano33_usb_{metric}",
            "state_topic": MQTT_STATE_TOPIC,
            "value_template": "{{ value_json." + value_key + " }}",
            "availability_topic": MQTT_AVAILABILITY_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "state_class": "measurement",
            "device": device,
        }
        topic = f"{DISCOVERY_PREFIX}/sensor/nano33_usb/{metric}/config"
        client.publish(topic, json.dumps(config), qos=1, retain=True)

    saturation_config = {
        "name": "Light Saturated",
        "unique_id": "nano33_usb_light_saturated",
        "state_topic": MQTT_STATE_TOPIC,
        "value_template": "{{ 'ON' if value_json.light_saturated else 'OFF' }}",
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability_topic": MQTT_AVAILABILITY_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device_class": "problem",
        "entity_category": "diagnostic",
        "device": device,
    }
    topic = f"{DISCOVERY_PREFIX}/binary_sensor/nano33_usb/light_saturated/config"
    client.publish(topic, json.dumps(saturation_config), qos=1, retain=True)


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    if os.environ.get("MQTT_USERNAME"):
        client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ.get("MQTT_PASSWORD", ""))

    client.will_set(MQTT_AVAILABILITY_TOPIC, "offline", qos=1, retain=True)

    def on_connect(connected_client, userdata, flags, reason_code):
        if reason_code != 0:
            LOGGER.error("MQTT connection rejected: %s", reason_code)
            return
        LOGGER.info("Connected to MQTT broker")
        connected_client.publish(MQTT_AVAILABILITY_TOPIC, "online", qos=1, retain=True)
        publish_discovery(connected_client)

    def on_disconnect(disconnected_client, userdata, reason_code):
        LOGGER.warning("MQTT disconnected: %s", reason_code)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"]), keepalive=60)
    client.loop_start()
    return client


def read_serial_forever(serial_port: str, client: mqtt.Client) -> None:
    while True:
        try:
            with serial.Serial(serial_port, 115200, timeout=5) as port:
                LOGGER.info("Reading Nano sensor data from %s", serial_port)
                client.publish(MQTT_AVAILABILITY_TOPIC, "online", qos=1, retain=True)
                while True:
                    raw_line = port.readline()
                    if not raw_line:
                        continue

                    try:
                        line = raw_line.decode("utf-8").strip()
                        reading = parse_reading(line)
                    except (UnicodeDecodeError, ValueError, KeyError) as error:
                        LOGGER.warning("Ignoring invalid serial line %r: %s", raw_line, error)
                        continue

                    result = client.publish(
                        MQTT_STATE_TOPIC,
                        json.dumps(reading),
                        qos=1,
                        retain=True,
                    )
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        LOGGER.info("Published %s", reading)
                    else:
                        LOGGER.warning("MQTT publish queued with status %s", result.rc)
        except serial.SerialException as error:
            LOGGER.warning("Cannot open/read %s: %s", serial_port, error)
            client.publish(MQTT_AVAILABILITY_TOPIC, "offline", qos=1, retain=True)
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial-port", required=True)
    args = parser.parse_args()

    client = create_mqtt_client()
    try:
        read_serial_forever(args.serial_port, client)
    finally:
        client.publish(MQTT_AVAILABILITY_TOPIC, "offline", qos=1, retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
