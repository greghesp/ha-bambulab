import json
import logging

from pathlib import Path
from enum import (
    Enum,
    IntEnum,
)

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
    START_TIME = 10,
    AMS_TEMPERATURE = 11,
    CAMERA_RTSP = 13,
    START_TIME_GENERATED = 14,
    CAMERA_IMAGE = 15,
    DOOR_SENSOR = 16,
    MANUAL_MODE = 17,
    AMS_FILAMENT_REMAINING = 18,
    SET_TEMPERATURE = 19,


class FansEnum(Enum):
    PART_COOLING = 1,
    AUXILIARY = 2,
    CHAMBER = 3,
    HEATBREAK = 4,


class TempEnum(Enum):
    HEATBED = 1,
    NOZZLE = 2


CURRENT_STAGE_IDS = {
    "default": "unknown",
    0: "printing",
    1: "auto_bed_leveling",
    2: "heatbed_preheating",
    3: "sweeping_xy_mech_mode",
    4: "changing_filament",
    5: "m400_pause",
    6: "paused_filament_runout",
    7: "heating_hotend",
    8: "calibrating_extrusion",
    9: "scanning_bed_surface",
    10: "inspecting_first_layer",
    11: "identifying_build_plate_type",
    12: "calibrating_micro_lidar", # DUPLICATED?
    13: "homing_toolhead",
    14: "cleaning_nozzle_tip",
    15: "checking_extruder_temperature",
    16: "paused_user",
    17: "paused_front_cover_falling",
    18: "calibrating_micro_lidar", # DUPLICATED?
    19: "calibrating_extrusion_flow",
    20: "paused_nozzle_temperature_malfunction",
    21: "paused_heat_bed_temperature_malfunction",
    22: "filament_unloading",
    23: "paused_skipped_step",
    24: "filament_loading",
    25: "calibrating_motor_noise",
    26: "paused_ams_lost",
    27: "paused_low_fan_speed_heat_break",
    28: "paused_chamber_temperature_control_error",
    29: "cooling_chamber",
    30: "paused_user_gcode",
    31: "motor_noise_showoff",
    32: "paused_nozzle_filament_covered_detected",
    33: "paused_cutter_error",
    34: "paused_first_layer_error",
    35: "paused_nozzle_clog",
    # X1 returns -1 for idle
    -1: "idle",  # DUPLICATED
    # P1 returns 255 for idle
    255: "idle", # DUPLICATED
}

CURRENT_STAGE_OPTIONS = list(set(CURRENT_STAGE_IDS.values())) # Conversion to set first removes the duplicates

GCODE_STATE_OPTIONS = [
    "failed",
    "finish",
    "idle",
    "init",
    "offline",
    "pause",
    "prepare",
    "running",
    "slicing",
    "unknown"
]

SPEED_PROFILE = {
    1: "silent",
    2: "standard",
    3: "sport",
    4: "ludicrous"
}

PRINT_TYPE_OPTIONS = {
    "cloud",
    "local",
    "idle",
    "system",
    "unknown"
}


def load_dict(filename: str) -> dict:
    with open(filename) as f:
        return json.load(f);


FILAMENT_NAMES = load_dict(Path(__file__).with_name('filaments.json'))

HMS_SEVERITY_LEVELS = {
    "default": "unknown",
    1: "fatal",
    2: "serious",
    3: "common",
    4: "info"
}

HMS_MODULES = {
    "default": "unknown",
    0x05: "mainboard",
    0x0C: "xcam",
    0x07: "ams",
    0x08: "toolhead",
    0x03: "mc"
}

class SdcardState(Enum):
    NO_SDCARD                           = 0x00000000,
    HAS_SDCARD_NORMAL                   = 0x00000100,
    HAS_SDCARD_ABNORMAL                 = 0x00000200,
    SDCARD_STATE_NUM                    = 0x00000300,

class Home_Flag_Values(IntEnum):
    X_AXIS                              = 0x00000001,
    Y_AXIS                              = 0x00000002,
    Z_AXIS                              = 0x00000004,
    VOLTAGE220                          = 0x00000008,
    XCAM_AUTO_RECOVERY_STEP_LOSS        = 0x00000010,
    CAMERA_RECORDING                    = 0x00000020,
    # Gap
    AMS_CALIBRATE_REMAINING             = 0x00000080,
    SD_CARD_PRESENT                     = 0x00000100,
    SD_CARD_ABNORMAL                    = 0x00000200,
    AMS_AUTO_SWITCH                     = 0x00000400,
    # Gap
    XCAM_ALLOW_PROMPT_SOUND             = 0x00020000,
    WIRED_NETWORK                       = 0x00040000,
    FILAMENT_TANGLE_DETECT_SUPPORTED    = 0x00080000,
    FILAMENT_TANGLE_DETECTED            = 0x00100000,
    SUPPORTS_MOTOR_CALIBRATION          = 0x00200000,
    # Gap
    DOOR_OPEN                           = 0x00800000,
    # Gap
    INSTALLED_PLUS                      = 0x04000000,
    SUPPORTED_PLUS                      = 0x08000000,
    # Gap

class BambuUrl(Enum):
    LOGIN = 1,
    TFA_LOGIN = 2,
    EMAIL_CODE = 3,
    BIND = 4,
    SLICER_SETTINGS = 5,
    TASKS = 6,
    PROJECTS = 7,

BAMBU_URL = {
    BambuUrl.LOGIN: 'https://api.bambulab.com/v1/user-service/user/login',
    BambuUrl.TFA_LOGIN: 'https://bambulab.com/api/sign-in/tfa',
    BambuUrl.EMAIL_CODE: 'https://api.bambulab.com/v1/user-service/user/sendemail/code',
    BambuUrl.BIND: 'https://api.bambulab.com/v1/iot-service/api/user/bind',
    BambuUrl.SLICER_SETTINGS: 'https://api.bambulab.com/v1/iot-service/api/slicer/setting?version=1.10.0.89',
    BambuUrl.TASKS: 'https://api.bambulab.com/v1/user-service/my/tasks',
    BambuUrl.PROJECTS: 'https://api.bambulab.com/v1/iot-service/api/user/project',
}
