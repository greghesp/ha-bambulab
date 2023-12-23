[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Bambu Lab

A Home Assistant Integration for Bambu Lab printers

## Contribution

Want to contribute to ha-bambulab? Great!  We have a few small asks though!

- Please do not fork and PR against the `main` branch
- Use the `develop` branch, this is our working area. Anything in the `main` branch should be considered live, released
  code.
- Please name your commits accordingly, and add some context as to what you have added.

If you feel this integration was valuable, you can make buy me a coffee at https://Ko-fi.com/adriangarside

## Setup

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greghesp&repository=ha-bambulab&category=Integration)

To install, add this Github Repo to the HACS Custom Repositories, or click the badge above.

For configuration, you'll ideally use your Bambu Credentials for the simplest setup. You can then optionally provide the printer IP address to enable local direct to printer connection and to enable the P1/A1 camera support. 

However the Bambu cloud connection doesn't support 2FA and passwordless social media accounts at this time. And it obviously does not support printers explicitly set to lan mode. If you fall into any of these, select the lan mode connection option. You will need to provide:
- The printer type
- Printer Serial Number - can be found in the printer settings or in Bambu Studio 
- Local printer IP address - can be found in the printer network settings
- LAN Access Code - can be found in the Printer settings

### Setup using Bambu Cloud w/ OAuth

If you signed up using any OAuth method, you need to set a password for your Bambu Cloud account:

- Login to the Bambu mobile app using OAuth.
- Tap the person icon at the bottom right.
- Tap Account Security > Change Password

This will allow you to set a password. Now you can login to the HA integration using your Bambu username and password
instead of OAuth.

## Features

### Fans

| Sensor        | Notes             |
|---------------|-------------------|
| Aux           |                   |
| Chamber       | Not on A1/A1 Mini |
| Cooling       |                   |

### Temperatures

| Sensor        | Notes             |
|---------------|-------------------|
| Bed           |                   |
| Target Bed    |                   |
| Chamber       | X1* only          |
| Nozzle        |                   |
| Target Nozzle |                   |

### Print Progress

| Sensor            | Notes                       |
|-------------------|-----------------------------|
| Current Layer     |                             |
| Total Layer Count |                             |
| Print Progress    |                             |
| Print Weight      |                             |
| Print Length      |                             |
| Print Bed Type    | Bed choice in the print job |
| Start Time        | Simulated on P1*/A1*        |
| Remainining Time  |                             |
| End Time          |                             |

### Status

| Sensor        | Notes             |
|---------------|-------------------|
| Current Stage |                   |
| Print Status  |                   |
| Cover Image   |                   |
| Print Weight  |                   |

### Miscellaneous

| Sensor            | Notes             |
|-------------------|-------------------|
| Speed Profile     |                   |
| Timelapse Active  |                   |

### AMS

| Sensor            | Notes             |
|-------------------|-------------------|
| Active tray       | If AMS present    |
| Active tray index | If AMS present    |

### Controls

| Lights              | Notes                                              |
|---------------------|----------------------------------------------------|
| Chamber Light       |                                                    |
| Pause               |                                                    |
| Resume              |                                                    |
| Stop                |                                                    |
| Manual Refresh Mode | P1*/A1* only and only available in local mqtt mode |

### AMS

| Sensor            | Notes             |
|-------------------|-------------------|
| Humidity Index    |                   |
| Temperature       | X1* only          |
| Tray 1            |                   |
| Tray 2            |                   |
| Tray 3            |                   |
| Tray 4            |                   |
|                   |                   |
| Tray attributes:  |                   |
| Color             |                   |
| Empty             |                   |
| K Value           | P1*/A1* only      |
| Max Nozzle Temp   |                   |
| Min Nozzle TEmp   |                   |
| Name              |                   |
| Type              |                   |

### External Spool

| Sensor            | Notes             |
|-------------------|-------------------|
| External Spool    |                   |
|                   |                   |
| Tray attributes:  |                   |
| Color             |                   |
| Empty             |                   |
| K Value           | P1*/A1* only      |
| Max Nozzle Temp   |                   |
| Min Nozzle TEmp   |                   |
| Name              |                   |
| Type              |                   |

### Diagnostics

| Sensor                    | Notes                                                          |
|---------------------------|----------------------------------------------------------------|
| Firmware Update Available |                                                                |
| Force Refresh             |                                                                |
| HMS Errors                | Attributes contain the error codes, descriptions and wiki URLs |
| MQTT connection mode      | Bambu Cloud or Local                                           |
| Online                    |                                                                |
| Wifi Signal               |                                                                |

### Cameras

| Sensor            | Notes             |
|-------------------|-------------------|
| Chamber           |                   |

### Automation device triggers

This integration implements a handful of device triggers to make some common automation scenarios a little easier.
See [device triggers](docs/DeviceTrigger.md).

### WLED Lights

Support for adding LED chamber lights via the [WLED](https://kno.wled.ge/).

- Requires the [WLED Home Assistant Integration](https://www.home-assistant.io/integrations/wled/) and the requisite LED
  lights and ESP device.
- Clink the link below to import the WLED blueprint

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fgreghesp%2Fha-bambulab%2Fblob%2Fmain%2Fblueprints%2Fwled_controller.yaml)

#### WLED Features

- LED lights automatically turn off when Bambu Lida is in use so as to not interfere
- LED lights turn red when there is an error in the printer
- LED lights turn blue when bed is auto leveling
- LED lights turn green when print is finished

## Example dashboard

You can find an amazing web configurator to easily create a Dashboard for your Bambu printer like the one below
at https://www.wolfwithsword.com/bambulab-home-assistant-dashboard/.

![image](docs/images/ExampleIntegration.png)
![image](docs/images/ExampleDevice1.png)
![image](docs/images/ExampleDevice2.png)

## Issues

### Diagnostic File

If you run into any issues, we now have built in diagnostics.  
To grab the latest information, hit the "Force Refresh Data" button under the Diagnostic section.

![image](docs/images/force-refresh.png)

Then on the device info page for the printer entity, you will see a "Download Diagnostics" button.
Make sure you upload this to your Bug ticket

![img.png](docs/images/diagnostics.png)

### Debug Logging

When logging a bug, always ensure you send us the debug logs. These can be enabled from the Integration page itself.
The debug logs will appear in the standard Home Assistant logs

![img.png](docs/images/debugging.png)
