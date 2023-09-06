![image](https://github.com/ianschmitz/ha-bambulab/assets/6355370/c4b9527c-ad9c-4a6a-a09e-b47bddbde5ce)[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Bambu Lab

A Home Assistant Integration for Bambu Lab printers

## Setup

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greghesp&repository=ha-bambulab&category=Integration)

To install, add this Github Repo to the HACS Custom Repositories, or click the badge above.

For now, you will need the following information:

- Printer IP
- LAN Access Code (Can be found on the Printer settings)
- Serial Number (Can be found in the printer settings or in Bambu Studio)

## Features

(:heavy_check_mark: Optional accessory)

### Sensors

| Sensor                    | X1C                | X1                 | P1P                | P1S                |
|---------------------------|--------------------|--------------------|--------------------|--------------------|
| Aux Fan Speed             | :white_check_mark: | :white_check_mark: | :heavy_check_mark: | :white_check_mark: |
| Bed Temperature           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Chamber Fan Speed         | :white_check_mark: | :white_check_mark: | :x:                | :white_check_mark: |
| Chamber Temperature       | :white_check_mark: | :white_check_mark: | :x:                | :x:                |
| Cooling Fan Speed         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Current Layer             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Current Stage             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| End Time                  | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Heatbreak Fan Speed       | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Target Temperature | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Nozzle Temperature        | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Progress            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Print Status              | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Remaining Time            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Speed Profile             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Start Time                | :white_check_mark: | :white_check_mark: | :x:                | :x:                |
| Target Bed Temperature    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Total Layer Count         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Timelapse Active          | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

If AMS(s) are present, an additional 'Current Tray' sensor is present on the Printer device.

### Lights

| Light         | X1C                | X1                 | P1P                | P1S                |  
|---------------|--------------------|--------------------|--------------------|--------------------|
| Chamber Light | :white_check_mark: | :white_check_mark: | :heavy_check_mark: | :white_check_mark: |


### Buttons

This currently exposes the following Buttons:

| Button | X1C                | X1                 | P1P                | P1S                |
|--------|--------------------|--------------------|--------------------|--------------------|
| Pause  | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Resume | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Stop   | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### AMS

| Sensor           | X1C                | X1                 | P1P                | P1S                |
|------------------|--------------------|--------------------|--------------------|--------------------|
| Humidity Index   | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 1           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 2           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 3           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray 4           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Tray Attributes: |                    |                    |                    |                    |
| Active           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Color            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Empty            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| K Value          | :x:                | :x:                | :white_check_mark: | :white_check_mark: |
| Max Nozzle Temp  | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Min Nozzle Temp  | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Name             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Type             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### External Spool

| Sensor          | X1C                | X1                 | P1P                | P1S                |
|-----------------|--------------------|--------------------|--------------------|--------------------|
| External Spool  | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Attributes:     |                    |                    |                    |                    |
| Active          | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Color           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| K Value         | :x:                | :x:                | :white_check_mark: | :white_check_mark: |
| Max Nozzle Temp | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Min Nozzle Temp | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Name            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Type            | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### Diagnostics

This currently exposes the following Diagnostic Sensors:

| Sensor        | X1C                | X1                 | P1P                | P1S                |
|---------------|--------------------|--------------------|--------------------|--------------------|
| Wifi Signal   | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| HMS Errors    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Attributes:   |                    |                    |                    |                    |
| Count         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 1-Error       | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 1-Wiki        | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 2-Error       | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 2-Wiki        | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| ... and so on |                    |                    |                    |                    |

### WLED Lights

Support for adding LED chamber lights via the [WLED](https://kno.wled.ge/).

- Requires the [WLED Home Assistant Integration](https://www.home-assistant.io/integrations/wled/) and the requisite LED lights and ESP device.
- Clink the link below to import the WLED blueprint

 [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fgreghesp%2Fha-bambulab%2Fblob%2Fmain%2Fblueprints%2Fwled_controller.yaml)

#### WLED Features

- LED lights automatically turn off when Bambu Lida is in use so as to not interfere
- LED lights turn red when there is an error in the printer
- LED lights turn blue when bed is auto leveling
- LED lights turn green when print is finished

### Cameras

Camera functionality is currently only supported for the X1C

If you want to see this changed, please comment and vote
on [this BambuStudio issue](https://github.com/bambulab/BambuStudio/issues/1536)

| Camera  | X1C                | X1                 | P1P | P1S |
|---------|--------------------|--------------------|-----|-----|
| Chamber | :white_check_mark: | :white_check_mark: | :x: | :x: |

## Release Notes

Please check `release_notes.md`
