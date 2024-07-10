import json
import logging

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


class FansEnum(Enum):
    PART_COOLING = 1,
    AUXILIARY = 2,
    CHAMBER = 3,
    HEATBREAK = 4,


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


FILAMENT_NAMES = load_dict("./filaments.json")

HMS_ERRORS = load_dict("./hms_errors.json")

# These errors cover those that are AMS and/or slot specific.
# 070X_xYxx_xxxx_xxxx = AMS X (0 based index) Slot Y (0 based index) has the error.
HMS_AMS_ERRORS = {
    "0700_0100_0001_0001": "AMS1 assist motor has slipped. The extrusion wheel may be worn down, or the filament may be too thin.",
    "0700_0100_0001_0003": "AMS1 assist motor torque control is malfunctioning. The current sensor may be faulty.",
    "0700_0100_0001_0004": "AMS1 assist motor speed control is malfunctioning. The speed sensor may be faulty.",
    "0700_0100_0002_0002": "AMS1 assist motor is overloaded. The filament may be tangled or stuck.",
    "0700_0200_0001_0001": "AMS1 filament speed and length error. The filament odometry may be faulty.",
    "0700_1000_0001_0001": "AMS1 slot 1 motor has slipped. The extrusion wheel may be malfunctioning, or the filament may be too thin.",
    "0700_1000_0001_0003": "AMS1 slot 1 motor torque control is malfunctioning. The current sensor may be faulty.",
    "0700_1000_0002_0002": "AMS1 slot 1 motor is overloaded. The filament may be tangled or stuck.",
    "0700_2000_0002_0001": "AMS1 slot 1 filament has run out.",
    "0700_2000_0002_0002": "AMS1 slot 1 is empty.",
    "0700_2000_0002_0003": "AMS1 slot 1 filament may be broken in AMS.",
    "0700_2000_0002_0004": "AMS1 slot 1 filament may be broken in the tool head.",
    "0700_2000_0002_0005": "AMS1 slot 1 filament has run out, and purging the old filament went abnormally, please check whether the filament is stuck in the tool head.",
    "0700_2000_0003_0001": "AMS1 slot 1 filament has run out. Please wait while old filament is purged.",
    "0700_2000_0003_0002": "AMS1 slot 1 filament has run out and automatically switched to the slot with the same filament.",
    "0700_6000_0002_0001": "AMS1 slot 1 is overloaded. The filament may be tangled or the spool may be stuck.",
}

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

