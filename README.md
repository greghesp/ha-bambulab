[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Bambu Lab

A Home Assistant Integration for Bambu Lab printers

## Setup

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greghesp&repository=ha-bambulab&category=Integration)

To install, add this Github Repo to the HACS Custom Repositories, or click the badge above.

For now, you will need the following information:

Cloud Mode MQTT connection:
- Registed Bambu email address & password.
- If you used an OAuth solution like a google account and you can add a password to that account, you can use that here.
- Your full credentials will not be saved but an authentication token that's generated using them will be saved into the home assistant store.
- The token expires after 360 days. You can re-auth using the configuration button on the integrations page.

Lan mode MQTT connection:
- Printer IP
- LAN Access Code (Can be found on the Printer settings)

Both:
- Serial Number (Can be found in the printer settings or in Bambu Studio)

### P1P Owners

In the latest firmware update, Bambu Lab added back the ability to connect to the MQTT een in cloud mode. But the ability to use cloud MQTT will remain in case that changes again in a future update.

## Features

(:heavy_check_mark: Optional accessory)

### Sensors

| Sensor                    | X1C                | X1                 | P1P                | 
|---------------------------|--------------------|--------------------|--------------------|
| Aux Fan Speed             | :white_check_mark: | :white_check_mark: | :heavy_check_mark: |
| Bed Temperature 	        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Chamber Fan Speed	        | :white_check_mark: | :white_check_mark: | :x:                |
| Chamber Temperature       | :white_check_mark: | :white_check_mark: | :x:                |
| Cooling Fan Speed	        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Current Layer	            | :white_check_mark: | :white_check_mark: | :x:                |
| Current Stage	            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| End Time                  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Heatbreak Fan Speed       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Target Temperature	| :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Temperature        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Progress            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Status	            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Remaining Time            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Speed Profile             | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Start Time                | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Target Bed Temperature    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Total Layer Count         | :white_check_mark: | :white_check_mark: | :x:                |

If AMS(s) are present, an additional 'Current Tray' sensor is present on the Printer device.

### Lights

| Sensor                    | X1C                | X1                 | P1P                | 
|---------------------------|--------------------|--------------------|--------------------|
| Chamber Light             | :white_check_mark: | :white_check_mark: | :heavy_check_mark: |

### Buttons

This currently exposes the following Buttons:

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Pause	                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Resume                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Stop	                    | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### AMS

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Humidity Index            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Active           | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Color            | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 K Value          | :x:                | :x:                | :white_check_mark: |
| Tray 1-4 Max Nozzle Temp  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Min Nozzle Temp  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Name             | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Sub Brands       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1-4 Type             | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### External Spool (P1P only)

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Active                    | :x:                | :x:                | :white_check_mark: |
| Color                     | :x:                | :x:                | :white_check_mark: |
| K Value                   | :x:                | :x:                | :white_check_mark: |
| Max Nozzle Temp           | :x:                | :x:                | :white_check_mark: |
| Min Nozzle Temp           | :x:                | :x:                | :white_check_mark: |
| Name                      | :x:                | :x:                | :white_check_mark: |
| Sub Brands                | :x:                | :x:                | :white_check_mark: |

### Diagnostics

This currently exposes the following Diagnostic Sensors:

| Sensor                    | X1C                | X1                 | P1P                |
|---------------------------|--------------------|--------------------|--------------------|
| Wifi Signal               | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### Cameras

Cameras are currently not supported across any Bambu Lab device, due to them using a proprietary streaming
implementation.

If you want to see this changed, please comment and vote
on [this BambuStudio issue](https://github.com/bambulab/BambuStudio/issues/1536)

## Release Notes

Please check `release_notes.md`
