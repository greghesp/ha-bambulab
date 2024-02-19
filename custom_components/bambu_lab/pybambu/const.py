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
    "local",
    "cloud",
    "idle"
}

FILAMENT_NAMES = {
    "default": "Unknown",
    "GFB00": "Bambu ABS",
    "GFB01": "Bambu ASA",
    "GFN03": "Bambu PA-CF",
    "GFN05": "Bambu PA6-CF",
    "GFN04": "Bambu PAHT-CF",
    "GFC00": "Bambu PC",
    "GFT01": "Bambu PET-CF",
    "GFG00": "Bambu PETG Basic",
    "GFG50": "Bambu PETG-CF",
    "GFA11": "Bambu PLA Aero",
    "GFA00": "Bambu PLA Basic",
    "GFA03": "Bambu PLA Impact",
    "GFA07": "Bambu PLA Marble",
    "GFA01": "Bambu PLA Matte",
    "GFA02": "Bambu PLA Metal",
    "GFA05": "Bambu PLA Silk",
    "GFA08": "Bambu PLA Sparkle",
    "GFA09": "Bambu PLA Tough",
    "GFA50": "Bambu PLA-CF",
    "GFS03": "Bambu Support For PA/PET",
    "GFS02": "Bambu Support For PLA",
    "GFS01": "Bambu Support G",
    "GFS00": "Bambu Support W",
    "GFU01": "Bambu TPU 95A",
    "GFB99": "Generic ABS",
    "GFB98": "Generic ASA",
    "GFS98": "Generic HIPS",
    "GFN98": "Generic PA-CF",
    "GFN99": "Generic PA",
    "GFC99": "Generic PC",
    "GFG99": "Generic PETG",
    "GFG98": "Generic PETG-CF",
    "GFL99": "Generic PLA",
    "GFL95": "Generic PLA-High Speed",
    "GFL96": "Generic PLA Silk",
    "GFL98": "Generic PLA-CF",
    "GFS99": "Generic PVA",
    "GFU99": "Generic TPU",
    "GFL05": "Overture Matte PLA",
    "GFL04": "Overture PLA",
    "GFB60": "PolyLite ABS",
    "GFB61": "PolyLite ASA",
    "GFG60": "PolyLite PETG",
    "GFL00": "PolyLite PLA",
    "GFL01": "PolyTerra PLA",
    "GFL03": "eSUN PLA+",
    "GFSL99_01": "Generic PLA Silk",
    "GFSL99_12": "Generic PLA Silk",
    "GFA12": "Bambu PLA Glow",
    "GFT97": "Generic PPS",
    "GFT98": "Generic PPS-CF",
    "GFU00": "Bambu TPU 95A HF",
}

# TODO: Update error lists with data from https://e.bambulab.com/query.php?lang=en
HMS_ERRORS = {
    "0300_1000_0002_0001": "The 1st order mechanical resonance mode of X axis is low.",
    "0300_1000_0002_0002": "The 1st order mechanical resonance mode of X axis differ much...",
    "0300_0F00_0001_0001": "The accelerometer data is unavailable",
    "0300_0D00_0001_000B": "The Z axis motor seems got stuck when moving up",
    "0300_0D00_0001_0002": "Hotbed homing failed. The environmental vibration is too great",
    "0300_0D00_0001_0003": "The build plate is not placed properly ...",
    "0300_0D00_0002_0001": "Heatbed homing abnormal. There may be a bulge on the ...",
    "0300_0A00_0001_0005": "the static voltage of force sensor 1/2/3 is not 0 ...",
    "0300_0A00_0001_0004": "External disturbance was detected when testing the force sensor",
    "0300_0A00_0001_0003": "The sensitivity of heatbed force sensor 1/2/3 is too low....",
    "0300_0A00_0001_0002": "The sensitivity of heatbed force sensor 1/2/3 is low...",
    "0300_0A00_0001_0001": "The sensitivity of heatbed force sensor 1/2/3 is too high...",
    "0300_0400_0002_0001": "The speed of part cooling fan if too slow or stopped ...",
    "0300_0300_0002_0002": "The speed of hotend fan is slow ...",
    "0300_0300_0001_0001": "The speed of the hotend fan is too slow or stopped...",
    "0300_0600_0001_0001": "Motor-A has an open-circuit. There may be a loose connection, or the motor may have failed.",
    "0300_0600_0001_0002": "Motor-A has a short-circuit. It may have failed.",
    "0300_0600_0001_0003": "The resistance of Motor-A is abnormal, the motor may have failed.",
    "0300_0100_0001_0001": "The heatbed temperature is abnormal, the heater may have a short circuit.",
    "0300_0100_0001_0002": "The heatbed temperature is abnormal, the heater may have an open circuit, or the thermal switch may be open.",
    "0300_0100_0001_0003": "The heatbed temperature is abnormal, the heater is over temperature.",
    "0300_0100_0001_0006": "The heatbed temperature is abnormal, the sensor may have a short circuit.",
    "0300_0100_0001_0007": "The heatbed temperature is abnormal, the sensor may have an open circuit.",
    "0300_1300_0001_0001": "The current sensor of Motor-A is abnormal. This may be caused by a failure of the hardware sampling circuit.",
    "0300_4000_0002_0001": "Data transmission over the serial port is abnormal, the software system may be faulty.",
    "0300_4100_0001_0001": "The system voltage is unstable, triggering the power failure protection function.",
    "0300_0200_0001_0001": "The nozzle temperature is abnormal, the heater may be short circuit.",
    "0300_0200_0001_0002": "The nozzle temperature is abnormal, the heater may be open circuit.",
    "0300_0200_0001_0003": "The nozzle temperature is abnormal, the heater is over temperature.",
    "0300_0200_0001_0006": "The nozzle temperature is abnormal, the sensor may be short circuit.",
    "0300_0200_0001_0007": "The nozzle temperature is abnormal, the sensor may be open circuit.",
    "0300_1200_0002_0001": "The front cover of the toolhead fell off.",
    "0C00_0100_0001_0001": "The Micro Lidar camera is offline.",
    "0C00_0100_0002_0002": "The Micro Lidar camera is malfunctioning.",
    "0C00_0100_0001_0003": "Synchronization between Micro Lidar camera and MCU is abnormal.",
    "0C00_0100_0001_0004": "The Micro Lidar camera lens seems to be dirty.",
    "0C00_0100_0001_0005": "Micro Lidar OTP parameter is abnormal.",
    "0C00_0100_0002_0006": "Micro Lidar extrinsic parameter abnormal.",
    "0C00_0100_0002_0007": "Micro Lidar laser parameters are drifted.",
    "0C00_0100_0002_0008": "Failed to get image from chamber camera.",
    "0C00_0100_0001_0009": "Chamber camera dirty.",
    "0C00_0100_0001_000A": "The Micro Lidar LED may be broken.",
    "0C00_0100_0001_000B": "Failed to calibrate Micro Lidar.",
    "0C00_0200_0001_0001": "The horizontal laser is not lit.",
    "0C00_0200_0002_0002": "The horizontal laser is too thick.",
    "0C00_0200_0002_0003": "The horizontal laser is not bright enough.",
    "0C00_0200_0002_0004": "Nozzle height seems too low.",
    "0C00_0200_0001_0005": "A new Micro Lidar is detected.",
    "0C00_0200_0002_0006": "Nozzle height seems too high.",
    "0C00_0300_0002_0001": "Filament exposure metering failed.",
    "0C00_0300_0002_0002": "First layer inspection terminated due to abnormal lidar data.",
    "0C00_0300_0002_0004": "First layer inspection not supported for current print.",
    "0C00_0300_0002_0005": "First layer inspection timeout.",
    "0C00_0300_0003_0006": "Purged filaments may have piled up.",
    "0C00_0300_0003_0007": "Possible first layer defects.",
    "0C00_0300_0003_0008": "Possible spaghetti defects were detected.",
    "0C00_0300_0001_0009": "The first layer inspection module rebooted abnormally.",
    "0C00_0300_0003_000B": "Inspecting first layer.",
    "0C00_0300_0002_000C": "The build plate localization marker is not detected.",
    "0500_0100_0002_0001": "The media pipeline is malfunctioning.",
    "0500_0100_0002_0002": "USB camera is not connected.",
    "0500_0100_0002_0003": "USB camera is malfunctioning.",
    "0500_0100_0003_0004": "Not enough space in SD Card.",
    "0500_0100_0003_0005": "Error in SD Card.",
    "0500_0100_0003_0006": "Unformatted SD Card.",
    "0500_0200_0002_0001": "Failed to connect internet, please check the network connection.",
    "0500_0200_0002_0002": "Failed to login device.",
    "0500_0200_0002_0004": "Unauthorized user.",
    "0500_0200_0002_0006": "Liveview service is malfunctioning.",
    "0500_0300_0001_0001": "The MC module is malfunctioning. Please restart the device.",
    "0500_0300_0001_0002": "The toolhead is malfunctioning. Please restart the device.",
    "0500_0300_0001_0003": "The AMS module is malfunctioning. Please restart the device.",
    "0500_0300_0001_000A": "System state is abnormal. Please restore factory settings.",
    "0500_0300_0001_000B": "The screen is malfunctioning.",
    "0500_0300_0002_000C": "Wireless hardware error. Please turn off/on WiFi or restart the device.",
    "0500_0400_0001_0001": "Failed to download print job. Please check your network connection.",
    "0500_0400_0001_0002": "Failed to report print state. Please check your network connection.",
    "0500_0400_0001_0003": "The content of print file is unreadable. Please resend the print job.",
    "0500_0400_0001_0004": "The print file is unauthorized.",
    "0500_0400_0001_0006": "Failed to resume previous print.",
    "0500_0400_0002_0007": "The bed temperature exceeds the filament's vitrification temperature, which may cause a nozzle clog.",
    "0700_4000_0002_0001": "The filament buffer signal lost, the cable or position sensor may be malfunctioning.",
    "0700_4000_0002_0002": "The filament buffer position signal error, the position sensor may be malfunctioning.",
    "0700_4000_0002_0003": "The AMS Hub communication is abnormal, the cable may be not well connected.",
    "0700_4000_0002_0004": "The filament buffer signal is abnormal, the spring may be stuck.",
    "0700_4500_0002_0001": "The filament cutter sensor is malfunctioning. The sensor may be disconnected or damaged.",
    "0700_4500_0002_0002": "The filament cutter's cutting distance is too large. The XY motor may lose steps.",
    "0700_4500_0002_0003": "The filament cutter handle has not released. The handle or blade may be stuck.",
    "0700_5100_0003_0001": "AMS is disabled, please load filament from spool holder.",
    "07FF_2000_0002_0001": "External filament has run out, please load a new filament.",
    "07FF_2000_0002_0002": "External filament is missing, please load a new filament.",
    "07FF_2000_0002_0004": "Please pull out the filament on the spool holder from the extruder.",
}

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

