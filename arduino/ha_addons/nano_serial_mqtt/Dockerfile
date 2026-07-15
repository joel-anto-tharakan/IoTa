FROM ghcr.io/home-assistant/base:latest

LABEL \
    io.hass.version="1.0.0" \
    io.hass.type="app" \
    io.hass.arch="aarch64|amd64"

RUN \
    apk add --no-cache python3 py3-pip \
    && pip3 install --no-cache-dir --break-system-packages mpremote paho-mqtt pyserial

COPY run.sh /
COPY nano_serial_mqtt.py /app/nano_serial_mqtt.py
COPY nano_main.py /app/nano_main.py

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
