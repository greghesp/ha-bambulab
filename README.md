[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Bambu Lab

A Home Assistant Integration for Bambu Lab printers

## Setup

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greghesp&repository=ha-bambulab&category=Integration)

To install, add this Github Repo to the HACS Custom Repositories, or click the badge above.

For now, you will need the following information:

Cloud Mode MQTT connection:
- Registed Bambu email address & password.
- Your full credentials will not be saved but an authentication token that's generated using them will be saved into the home assistant store.
- The token expires after 360 days. You can re-auth using the configuration button on the integrations page.

If you signed up using any OAuth method, you need to set a password for your Bambu Cloud account:
- Login to the Bambu mobile app using OAuth.
- Tap the person icon at the bottom right.
- Tap Account Security > Change Password
Now you can login to the HA integration using your Bambu username and that password.

Lan mode MQTT connection:
- Printer IP
- LAN Access Code (Can be found on the Printer settings)

> For the X1C, this mode also works without the printer needing to be in LAN mode

Both:
- Serial Number (Can be found in the printer settings or in Bambu Studio)

### P1P Owners

In the latest firmware update, Bambu Lab added back the ability to connect to the local MQTT server on the printer even in cloud mode. But the ability to use cloud MQTT will remain in case that changes again in a future update.

## Features

(:heavy_check_mark: Optional accessory)

### Sensors

| Sensor                    | X1C                | X1                 | P1P                | 
|---------------------------|--------------------|--------------------|--------------------|
| Aux Fan Speed             | :white_check_mark: | :white_check_mark: | :heavy_check_mark: |
| Bed Temperature           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Chamber Fan Speed         | :white_check_mark: | :white_check_mark: | :x:                |
| Chamber Temperature       | :white_check_mark: | :white_check_mark: | :x:                |
| Cooling Fan Speed         | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Current Layer             | :white_check_mark: | :white_check_mark: | :x:                |
| Current Stage             | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| End Time                  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Heatbreak Fan Speed       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Target Temperature | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Temperature        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Progress            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Status              | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Remaining Time            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Speed Profile             | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Start Time                | :white_check_mark: | :white_check_mark: | :x:                |
| Target Bed Temperature    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Total Layer Count         | :white_check_mark: | :white_check_mark: | :x:                |
| Timelapse Active          | :white_check_mark: | :white_check_mark: | :white_check_mark: |

If AMS(s) are present, an additional 'Current Tray' sensor is present on the Printer device.

### Lights

| Sensor                    | X1C                | X1                 | P1P                | 
|---------------------------|--------------------|--------------------|--------------------|
| Chamber Light             | :white_check_mark: | :white_check_mark: | :heavy_check_mark: |

### Buttons

This currently exposes the following Buttons:

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Pause                     | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Resume                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Stop                      | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### AMS

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Humidity Index            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 2                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 3                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 4                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray Attributes:          |                    |                    |                    |
| Active                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Color                     | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Empty                     | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| K Value                   | :x:                | :x:                | :white_check_mark: |
| Max Nozzle Temp           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Min Nozzle Temp           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Name                      | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Type                      | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### External Spool

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| External Spool            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Attributes:               |                    |                    |                    |
| Active                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Color                     | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| K Value                   | :x:                | :x:                | :white_check_mark: |
| Max Nozzle Temp           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Min Nozzle Temp           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Name                      | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Type                      | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### Diagnostics

This currently exposes the following Diagnostic Sensors:

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Wifi Signal               | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| HMS Errors                | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Attributes:               |                    |                    |                    |
| Count                     | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 1-Error                   | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 1-Wiki                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 2-Error                   | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 2-Wiki                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| ... and so on             |                    |                    |                    |

### Cameras

Cameras are currently not supported across any Bambu Lab device, due to them using a proprietary streaming
implementation.

If you want to see this changed, please comment and vote
on [this BambuStudio issue](https://github.com/bambulab/BambuStudio/issues/1536)

## Release Notes

Please check `release_notes.md`
