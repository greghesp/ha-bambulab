from enum import Enum
import logging

LOGGER = logging.getLogger(__package__)

class Features(Enum):
    AUX_FAN = 1,
    CHAMBER_LIGHT = 2,
    CHAMBER_FAN = 3,
    CHAMBER_TEMPERATURE = 4,
    CURRENT_STAGE = 5,
    PRINT_LAYERS = 6,
    AMS = 7,
    EXTERNAL_SPOOL = 8,
    K_VALUE = 9,

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
    "GFA00": "Bambu PLA Basic",
    "GFA01": "Bambu PLA Matte",
    "GFB00": "Bambu ABS",
    "GFB98": "Generic ASA",
    "GFB99": "Generic ABS",
    "GFC00": "Bambu PC",
    "GFC99": "Generic PC",
    "GFG99": "Generic PETG",
    "GFL00": "PolyLite PLA",
    "GFL01": "PolyTerra PLA",
    "GFL98": "Generic PLA-CF",
    "GFL99": "Generic PLA",
    "GFN03": "Bambu PC-CF",
    "GFN98": "Generic PA-CF",
    "GFN99": "Generic PA",
    "GFS00": "Bambu Support W",
    "GFS01": "Bambu Support G",
    "GFS99": "Generic PVA",
    "GFSL99_01": "Generic PLA Silk",
    "GFSL99_12": "Generic PLA Silk",
    "GFU01": "Bambu TPU 95A",
    "GFU99": "Generic TPU",
}