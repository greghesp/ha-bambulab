"""MQTT Commands"""
CHAMBER_LIGHT_ON = {
    "system": {"sequence_id": "0", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "on",
               "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0}}
CHAMBER_LIGHT_OFF = {
    "system": {"sequence_id": "0", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "off",
               "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0}}

SPEED_PROFILE_TEMPLATE = {"print": {"sequence_id": "0", "command": "print_speed", "param": ""}}

GET_VERSION = {"info": {"sequence_id": "0", "command": "get_version"}}

PAUSE = {"print": {"sequence_id": "0", "command": "pause"}}
RESUME = {"print": {"sequence_id": "0", "command": "resume"}}
STOP = {"print": {"sequence_id": "0", "command": "stop"}}

PUSH_ALL = {"pushing": {"sequence_id": "0", "command": "pushall"}}

START_PUSH = { "pushing": {"sequence_id": "0", "command": "start"}}

SEND_GCODE_TEMPLATE = {"print": {"sequence_id": "0", "command": "gcode_line", "param": ""}} # param = GCODE_EACH_LINE_SEPARATED_BY_\n
PRINT_PROJECT_FILE_TEMPLATE = {
                "print": {
                    "sequence_id": 0,
                    "command": "project_file",

                    "param": "", # param = f"Metadata/plate_1.gcode"
                    "url": "", # url = f"ftp://{file}"
                    "bed_type": "auto",
                    "timelapse": False,
                    "bed_leveling": True,
                    "flow_cali": True,
                    "vibration_cali": True,
                    "layer_inspect": True,
                    "use_ams": False,
                    "ams_mapping": [0],

                    "subtask_name": "",
                    "profile_id": "0",
                    "project_id": "0",
                    "subtask_id": "0",
                    "task_id": "0",
                }
            }

# X1 only currently
GET_ACCESSORIES = {"system": {"sequence_id": "0", "command": "get_accessories", "accessory_type": "none"}}

# A1 only
PROMPT_SOUND_ENABLE  = {"print" : {"sequence_id": "0", "command": "print_option", "sound_enable": True}}
PROMPT_SOUND_DISABLE = {"print" : {"sequence_id": "0", "command": "print_option", "sound_enable": False}}
                             