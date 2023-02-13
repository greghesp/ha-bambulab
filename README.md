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

| Sensor        	            | X1C                	 | X1  	                | P1P 	               |
|----------------------------|----------------------|----------------------|---------------------|
| Aux Fan Speed 	            | :heavy_check_mark: 	 | :heavy_check_mark: 	 | :x: 	               |
| Bed Temperature 	          | :heavy_check_mark:	  | :heavy_check_mark: 	 | :heavy_check_mark:	 |
| Chamber Fan Speed	         | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:x:                |
| Chamber Temperature	       | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:grey_question:    |
| Cooling Fan Speed	         | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Current Stage	             | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Heatbreak Fan Speed	       | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Nozzle Target Temperature	 | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Nozzle Temperature	        | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Print Progress	            | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Print Status	              | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Speed Profile              | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |
| Target Bed Temperature     | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |

### Buttons 
This currently exposes the following Buttons:

| Sensor        	 | X1C                	 | X1  	                | P1P 	               |
|-----------------|----------------------|----------------------|---------------------|
| Pause	          | :heavy_check_mark: 	 | :heavy_check_mark: 	 | :heavy_check_mark:  |
| Resume 	        | :heavy_check_mark:	  | :heavy_check_mark: 	 | :heavy_check_mark:	 |
| Stop	           | :heavy_check_mark:	  | :heavy_check_mark:	  | 	:heavy_check_mark: |

### Diagnostics 
This currently exposes the following Diagnostic Sensors:

| Sensor        	 | X1C                	 | X1  	                | P1P 	               |
|-----------------|----------------------|----------------------|---------------------|
| Wifi Signal	    | :heavy_check_mark: 	 | :heavy_check_mark: 	 | :heavy_check_mark:  |

### Cameras

Cameras are currently not supported across any Bambu Lab device