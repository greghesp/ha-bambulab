"""MQTT Commands"""
CHAMBER_LIGHT_ON = {
    "system": {"sequence_id": "2003", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "on",
               "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0}, "user_id": "123456789"}
CHAMBER_LIGHT_OFF = {
    "system": {"sequence_id": "2003", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "off",
               "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0}, "user_id": "123456789"}

SPEED_PROFILE_TEMPLATE = {"print": {"sequence_id": "2004", "command": "print_speed", "param": "2"}, "user_id": "1234567890"}

GET_VERSION = {"info": {"sequence_id": "20004", "command": "get_version"}, "user_id": "1234567890"}

PAUSE = {"print": {"sequence_id": "2008", "command": "pause"}, "user_id": "123456789"}
RESUME = {"print": {"sequence_id": "2009", "command": "resume"}, "user_id": "123456789"}
STOP = {"print": {"sequence_id": "2010", "command": "stop"}, "user_id": "123456789"}

PUSH_ALL = { "pushing": { "sequence_id": "1", "command": "pushall" }, "user_id": "1234567890" }
