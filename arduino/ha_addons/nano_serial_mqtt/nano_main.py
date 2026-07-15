# Persistent MicroPython firmware for Arduino Nano 33 BLE Sense Rev2.
# Save this on the Nano as main.py. It emits one sensor reading every 30 seconds.

import time
from machine import Pin, I2C
import hs3003
import lps22h
from apds9960.const import *
from apds9960 import uAPDS9960 as APDS9960

SAMPLE_INTERVAL_MS = 30000

# APDS9960 driver defaults. Keep these with every reading so lux calibration
# remains reproducible if the sensor configuration changes later.
LIGHT_GAIN = 4
LIGHT_INTEGRATION_MS = 103.0
LIGHT_SATURATION_COUNT = 37800
LUX_CALIBRATION_FACTOR = 1.0


def calculate_lux(red, green, blue):
    # Calibrate this estimate against a reference lux meter after mounting.
    estimated_lux = (
        (-0.32466 * red)
        + (1.57837 * green)
        - (0.73191 * blue)
    )
    return max(0.0, estimated_lux * LUX_CALIBRATION_FACTOR)

bus = I2C(1, scl=Pin(15), sda=Pin(14))
hs = hs3003.HS3003(bus)
lps = lps22h.LPS22H(bus)
apds = APDS9960(bus)

apds.enableLightSensor(interrupts=False)
time.sleep_ms(250)

# The LPS22H can report an unreliable first pressure value after startup.
lps.pressure()
time.sleep_ms(100)

while True:
    humidity_percent = hs.humidity()
    temperature_c = hs.temperature()
    pressure_hpa = lps.pressure()
    light_clear = apds.readAmbientLight()
    light_red = apds.readRedLight()
    light_green = apds.readGreenLight()
    light_blue = apds.readBlueLight()
    illuminance_lux = calculate_lux(light_red, light_green, light_blue)
    light_saturated = int(
        max(light_clear, light_red, light_green, light_blue)
        >= LIGHT_SATURATION_COUNT
    )

    print(
        "rH:%.2f,T:%.2f,Pressure:%.2f,LightClear:%d,LightRed:%d,"
        "LightGreen:%d,LightBlue:%d,Lux:%.2f,LightSaturated:%d,"
        "LightGain:%d,LightIntegrationMs:%.1f" % (
            humidity_percent,
            temperature_c,
            pressure_hpa,
            light_clear,
            light_red,
            light_green,
            light_blue,
            illuminance_lux,
            light_saturated,
            LIGHT_GAIN,
            LIGHT_INTEGRATION_MS,
        )
    )
    time.sleep_ms(SAMPLE_INTERVAL_MS)
