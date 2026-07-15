# LED Strip Setup

This folder contains the working files for the LEDnet/Magic Home Wi-Fi
controller used by the mini germination chamber. The strip is controlled
locally over the network. The vendor app is not required.

## Confirmed Working Setup

The current path is:

~~~text
Home Assistant
    |
    | Magic Home local integration
    | TCP port 5577
    v
LEDnet/Magic Home controller at 10.21.225.29
    |
    v
LED strip
~~~

The Home Assistant configuration was checked over the ssh ha terminal. The
controller is already registered and these are the live names from Home
Assistant:

| Item | Confirmed value |
| --- | --- |
| Home Assistant integration name | Magic Home |
| Home Assistant internal platform | flux_led |
| Integration title | Controller RGB 428851 |
| User-facing device name | Germination Chamber Light |
| Home Assistant entity | light.germination_chamber_germination_chamber_light |
| Home Assistant area | germination_chamber |
| Controller IP | 10.21.225.29 |
| Controller TCP port | 5577 |
| Controller MAC | E8:CA:50:42:88:51 |
| Manufacturer | Zengge |
| Model | Controller RGB (0x33) |
| Hardware version | AK001-ZJ21412 |
| Software version | 14.27 |

The controller entity reports RGB support. Home Assistant currently knows
these effects:

~~~text
blue_fade       blue_strobe       colorjump
colorloop       colorstrobe       cyan_fade
cyan_strobe     cycle_rgb         cycle_seven_colors
gb_cross_fade   green_fade        green_strobe
purple_fade     purple_strobe     rb_cross_fade
red_fade        red_strobe        rg_cross_fade
rgb_cross_fade  white_fade        white_strobe
yellow_fade     yellow_strobe     random
~~~

For germination experiments, use a static RGB colour and a repeatable
brightness rather than a moving or strobing effect.

## Files In This Folder

Only the files used by the working Wi-Fi controller are kept here:

| File | Purpose |
| --- | --- |
| LED_STRIP_SETUP.md | This setup and operating guide |
| led.py | Direct controller commands, discovery, scanning, and reachability checks |
| provision_lednet_wifi.py | Configure the controller onto a normal Wi-Fi network |

These are the only local files needed for the working Wi-Fi controller.

## Controller Network Details

The controller has two relevant network modes.

### Temporary setup mode

When it is waiting for Wi-Fi configuration, connect to:

~~~text
SSID: LEDnet0033428851
IP:   10.10.123.3
UDP:  48899
~~~

The controller identity observed during setup was:

~~~text
MAC:   E8:CA:50:42:88:51
Model: AK001-ZJ21412
~~~

### Normal Wi-Fi mode

After provisioning, the controller joins the destination network and listens
for lighting commands on:

~~~text
IP:   10.21.225.29
TCP:  5577
~~~

The IP address is assigned by DHCP and can change. Home Assistant currently
uses 10.21.225.29; reserve this address in the router or hotspot if that
feature is available.

## Provisioning Without the Vendor App

Use this while the computer is connected to the temporary
LEDnet0033428851 network.

Open PowerShell in this folder:

~~~powershell
cd C:\Users\Joel\Documents\CodexProjects\COMP6733\led_strip
~~~

Provision the controller onto the destination network used during setup:

~~~powershell
python .\provision_lednet_wifi.py "peepee poopoo"
~~~

The script prompts for the Wi-Fi password without displaying it. It then:

1. Finds the controller on UDP 48899.
2. Selects station mode.
3. Enables DHCP.
4. Sends the destination SSID and WPA2 password.
5. Reboots the controller.

Wait about 60 seconds after the reboot. The controller should leave the
temporary setup network and appear as a client on the destination Wi-Fi.

Useful options:

~~~powershell
# Use the known temporary setup address.
python .\provision_lednet_wifi.py "peepee poopoo" --target 10.10.123.3

# Prompting for the password is preferred. This form can expose the password
# in terminal history, so use it only when that is acceptable.
python .\provision_lednet_wifi.py "peepee poopoo" --password "YOUR_PASSWORD"
~~~

Do not store the real Wi-Fi password in this Markdown file or in a checked-in
script.

## Direct Terminal Commands

Run these commands from led_strip:

~~~powershell
# Discover the controller and cache the address.
python .\led.py scan

# Check that the cached or discovered controller is reachable.
python .\led.py status

# Turn the strip on and off.
python .\led.py on
python .\led.py off

# Set named colours.
python .\led.py red
python .\led.py green
python .\led.py blue
python .\led.py white
python .\led.py warmwhite
python .\led.py yellow
python .\led.py cyan
python .\led.py magenta
python .\led.py orange
python .\led.py purple
python .\led.py pink

# Set any RGB colour with hexadecimal notation.
python .\led.py "#00FFAA"
python .\led.py "#FFFFFF"

# List all named colours accepted by the script.
python .\led.py colors

# Set the warm-white channel from 0 to 255.
python .\led.py warmwhite 180

# Set the warm-white channel using a percentage from 0 to 100.
python .\led.py brightness 70

# Select a built-in controller effect.
python .\led.py preset 1

# Set effect speed from 1 to 100.
python .\led.py speed 50
~~~

The brightness command is a convenience wrapper for the controller's
warm-white channel. It is not a measurement of lux, PPFD, or PAR. For RGB
experiments, use a fixed hexadecimal colour and save the Home Assistant
brightness separately.

The built-in preset numbers are:

| Preset | Effect |
| ---: | --- |
| 1 | Seven-colour crossfade |
| 2 | Red fade |
| 3 | Green fade |
| 4 | Blue fade |
| 5 | Yellow fade |
| 6 | Cyan fade |
| 7 | Magenta fade |
| 8 | White fade |
| 9 | Seven-colour strobe |

## Discovery Cache

led.py scan first uses the LEDnet discovery message
HF-A11ASSISTHREAD on UDP 48899. It also scans likely local subnets for TCP
port 5577.

After a successful discovery, the address is cached outside this folder:

~~~text
Windows: %USERPROFILE%\.led_device.json
Linux:   ~/.led_device.json
~~~

If the controller receives a new DHCP address, clear the cache and scan again:

~~~powershell
Remove-Item "$env:USERPROFILE\.led_device.json" -ErrorAction SilentlyContinue
python .\led.py scan
~~~

## Home Assistant

The live Home Assistant configuration already contains the controller. It was
confirmed through the entity and device registries in /config/.storage over
the ssh ha terminal.

The device is configured as:

~~~text
Device:  Germination Chamber Light
Entity:  light.germination_chamber_germination_chamber_light
Host:    10.21.225.29
Port:    5577
Area:    germination_chamber
~~~

To operate it from the Home Assistant interface:

1. Open Settings -> Devices & services.
2. Open the Magic Home integration.
3. Select Germination Chamber Light.
4. Use the entity light.germination_chamber_germination_chamber_light in dashboards, automations, and scenes.

To inspect the current state and supported attributes, open:

~~~text
Developer Tools -> States
~~~

Search for:

~~~text
light.germination_chamber_germination_chamber_light
~~~

The integration reports RGB as its supported colour mode. Depending on the
current effect, the state attributes can include brightness, rgb_color,
effect, and the effect list shown near the top of this document.

Home Assistant controls this controller locally. The controller does not
measure light intensity, PPFD/PAR, temperature, electrical power, or plant
response. Add separate sensors if those values are needed.

## Saving Germination Light Recipes

Use Home Assistant scenes to save repeatable settings. The entity name below
is the confirmed live entity name:

~~~yaml
- name: Chamber Seedling White 70
  entities:
    light.germination_chamber_germination_chamber_light:
      state: "on"
      brightness: 180
      rgb_color: [255, 245, 220]

- name: Chamber Cool Blue Test
  entities:
    light.germination_chamber_germination_chamber_light:
      state: "on"
      brightness: 160
      rgb_color: [160, 200, 255]

- name: Chamber Red Blue Test
  entities:
    light.germination_chamber_germination_chamber_light:
      state: "on"
      brightness: 180
      rgb_color: [255, 40, 180]

- name: Chamber Lights Off
  entities:
    light.germination_chamber_germination_chamber_light:
      state: "off"
~~~

This list can be placed in scenes.yaml, or the same values can be entered
through the Home Assistant scene editor.

For each experiment, record:

~~~text
profile name
date and time
brightness
RGB or warm-white setting
effect and speed, if used
hours on per day
temperature and humidity
plant type and seed count
germination count and date
plant observations and photographs
~~~

The RGB values above are starting points for repeatable comparisons. They are
not calibrated horticultural recommendations. Keep the light distance, strip
position, photoperiod, temperature, humidity, and water conditions consistent
when comparing profiles.

## Troubleshooting

### Controller address changed

Connect to the same normal Wi-Fi network as the controller and run:

~~~powershell
python .\led.py scan
~~~

If the scan finds a new address, update the host used by the Home Assistant
Magic Home integration.

### The temporary setup network is visible

Connect to LEDnet0033428851 and run the provisioning command again. The
setup-mode address is normally 10.10.123.3.

### Home Assistant cannot reach the light

Run python .\led.py status from a computer on the same Wi-Fi network. Then
check that the Raspberry Pi and controller can communicate over TCP port 5577,
and that the Wi-Fi network allows wireless clients to communicate with one
another.

### The light is reachable but an attribute is missing

Inspect the entity in Developer Tools -> States. The controller exposes RGB
and effects, but the available attributes depend on the controller firmware
and the Home Assistant integration version.

## Protocol Summary

led.py sends the controller's binary Magic Home/LEDnet protocol over TCP.
Each command ends with a one-byte checksum calculated from the command bytes.

| Operation | Command bytes before checksum |
| --- | --- |
| On | 71 23 0F |
| Off | 71 24 0F |
| RGB colour | 31 RR GG BB 00 F0 0F |
| Warm white | 31 00 00 00 WW 0F 0F |
| Preset | 25 through 2D, followed by zero fields and 0F |
| Effect speed | 0F SS 00 00 00 00 0F |

RR, GG, BB, and WW are channel values from 0 to 255. The command-line speed
is limited to 1 through 100.

## References

- Home Assistant Magic Home integration: https://www.home-assistant.io/integrations/flux_led/
- Home Assistant scenes: https://www.home-assistant.io/integrations/scene/
- LEDnet/Magic Hue FAQ: https://faqsys.magichue.net:4489/faqIndex.html?appFrom=ZG001
