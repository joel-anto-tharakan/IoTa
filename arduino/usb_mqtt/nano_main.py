# Persistent MicroPython firmware for Arduino Nano 33 BLE Sense Rev2.
# Save this on the Nano as main.py. It emits one sensor reading every 30 seconds.

import time
from machine import Pin, I2C
import hs3003
import lps22h
from apds9960.const import *
from apds9960 import uAPDS9960 as APDS9960

SAMPLE_INTERVAL_MS = 30000

bus = I2C(1, scl=Pin(15), sda=Pin(14))
hs = hs3003.HS3003(bus)
lps = lps22h.LPS22H(bus)
apds = APDS9960(bus)

apds.enableLightSensor()
time.sleep_ms(250)

# The LPS22H can report an unreliable first pressure value after startup.
lps.pressure()
time.sleep_ms(100)

while True:
    humidity_percent = hs.humidity()
    temperature_c = hs.temperature()
    pressure_hpa = lps.pressure()
    ambient_light = apds.readAmbientLight()

    print(
        "rH:%.2f,T:%.2f,Pressure:%.2f,Light:%d" % (
            humidity_percent,
            temperature_c,
            pressure_hpa,
            ambient_light,
        )
    )
    time.sleep_ms(SAMPLE_INTERVAL_MS)
