from enum import Enum
import logging

LOGGER = logging.getLogger(__package__)

class Features(Enum):
    AUX_FAN = 1,
    CHAMBER_LIGHT = 2,
    CHAMBER_FAN = 3,
    CHAMBER_TEMPERATURE = 4,
    CURRENT_STAGE = 5,
    PRINT_LAYERS = 6

ACTION_IDS = {
    "default": "Unknown",
    -1: "Idle",
    0: "Printing",
    1: "Auto Bed Leveling",
    2: "Heatbed Preheating",
    3: "Sweeping XY Mech Mode",
    4: "Changing Filament",
    5: "M400 Pause",
    6: "Paused due to filament runout",
    7: "Heating Hotend",
    8: "Calibrating Extrusion",
    9: "Scanning Bed Surface",
    10: "Inspecting First Layer",
    11: "Identifying Build Plate Type",
    12: "Calibrating Micro Lidar",
    13: "Homing Toolhead",
    14: "Cleaning Nozzle Tip",
    15: "Checking Extruder Temperature",
    16: "Printing was paused by the user",
    17: "Pause of front cover falling",
    18: "Calibrating Micro Lidar",
    19: "Calibrating Extrusion Flow",
    20: "Paused due to nozzle temperature malfunction",
    21: "Paused due to heat bed temperature malfunction"
}

SPEED_PROFILE = {
    "default": "Unknown",
    1: "Silent",
    2: "Standard",
    3: "Sport",
    4: "Ludicrous"
}

FILAMENT_NAMES = {
    "default": "Unknown",
    "GFU99": "Generic TPU",
    "GFS99": "Generic PVA",
    "GFL98": "Generic PLA-CF",
    "GFL99": "Generic PLA",
    "GFG99": "Generic PETG",
    "GFC99": "Generic PC",
    "GFN98": "Generic PA-CF",
    "GFN99": "Generic PA",
    "GFB98": "Generic ASA",
    "GFB99": "Generic ABS",
    "GFU01": "Bambu TPU 95A",
    "GFS00": "Bambu Support W",
    "GFS01": "Bambu Support G",
    "GFA01": "Bambu PLA Matte",
    "GFA00": "Bambu PLA Basic",
    "GFC00": "Bambu PC",
    "GFN03": "Bambu PA-CF",
    "GFB00": "Bambu ABS",
    "GFL01": "PolyTerra PLA",
    "GFL00": "PolyLite PLA"
}