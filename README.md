[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Bambu Lab

> This is still a WIP.

## Setup

For now, you will need the following information:
- Printer IP
- LAN Access Code (Can be found on the Printer settings)
- Serial Number (Can be found in the printer settings or in Bambu Studio)

If you are running the latest firmware which requires TLS MQTT Support, please check the `Enable TLS` box

## Features

### Sensors 
This currently exposes the following Sensors (where applicable):

(:heavy_check_mark: Optional accessory)

| Sensor        	           | X1C               	  | X1  	               | P1P 	                | 
|----------------------------|----------------------|----------------------|----------------------|
| Aux Fan Speed 	           |  :white_check_mark:  |  :white_check_mark:  |  :heavy_check_mark:  |
| Bed Temperature 	         |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Chamber Fan Speed	         |  :white_check_mark:  |  :white_check_mark:  |  :heavy_check_mark:  |
| Chamber Temperature	       |  :white_check_mark:  |  :white_check_mark:  |  :x:                 |
| Cooling Fan Speed	         |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Current Stage	             |  :white_check_mark:  |  :white_check_mark:  |  :x:                 |
| Heatbreak Fan Speed	       |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Nozzle Target Temperature	 |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Nozzle Temperature	       |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Print Progress	           |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Print Status	             |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Speed Profile              |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |
| Target Bed Temperature     |  :white_check_mark:  |  :white_check_mark:  |  :white_check_mark:  |

### Buttons 
This currently exposes the following Buttons:

| Sensor        	| X1C                	 | X1  	                | P1P 	              |
|-----------------|----------------------|----------------------|---------------------|
| Pause	          | :white_check_mark: 	 | :white_check_mark:   | :white_check_mark:  |
| Resume 	        | :white_check_mark:	 | :white_check_mark:   | :white_check_mark:  |
| Stop	          | :white_check_mark:	 | :white_check_mark:	  | :white_check_mark:  |

### Diagnostics 
This currently exposes the following Diagnostic Sensors:

| Sensor          | X1C                	 | X1  	                | P1P 	              |
|-----------------|----------------------|----------------------|---------------------|
| Wifi Signal	    | :white_check_mark: 	 | :white_check_mark:   | :white_check_mark:  |

### Cameras

Cameras are currently not supported across any Bambu Lab device
