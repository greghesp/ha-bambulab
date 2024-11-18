"""Update the const.py file from https://e.bambulab.com/query.php?lang=en"""
from __future__ import annotations

import json
import os
import urllib.request


def check_for_file(path):
    """Verify const.py is where we expect it to be."""
    if not os.path.isfile(path):
        print("const.py not found, expected location '../custom_components/bambu_lab/pybambu/const.py' ")
        exit(1)


def download_json_data(json_url):
    """Download the JSON from Bambu"""
    req = urllib.request.Request(json_url, headers={'User-Agent' : "Magic Browser"}) 
    con = urllib.request.urlopen(req)
    return(con.read())
    

def write_new_file(file_to_write, file_contents):
    """Write the new const.py file"""
    file_handler = open(file_to_write, "w")
    file_handler.write(file_contents)
    file_handler.close()
    return


def process_json(json_data):
    """Process the JSON data and prep it for adding to const.py"""
    bambu_data = json.loads(json_data)
    HMS_ERROR = {}
    HMS_AMS_ERROR = {}
    PRINT_ERROR = {}
    for error_entry in bambu_data['data']['device_hms']['en']:
        # Check if this is an AMS error code, they start with 070
        code = f"{error_entry['ecode'][slice(0,4,1)].upper()}_{error_entry['ecode'][slice(4,8,1)].upper()}_{error_entry['ecode'][slice(8,12,1)].upper()}_{error_entry['ecode'][slice(12,16,1)].upper()}"
        value = error_entry['intro'].replace('\"', '\'').replace('\n', '').replace('  ', ' ')
        if error_entry['ecode'].startswith('070'):
            # Format is (including 4 spaces at the front)
            #   "WWWW_XXXX_YYYY_ZZZZ": "text",
            # Use the replace at the end because some of the fields have double quotes in them, just replace with single quotes
            HMS_AMS_ERROR[code] = value
        else:
            HMS_ERROR[code] = value

    for error_entry in bambu_data['data']['device_error']['en']:
        code = f"{error_entry['ecode'][slice(0,4,1)].upper()}_{error_entry['ecode'][slice(4,8,1)].upper()}"
        value = error_entry['intro'].replace('\"', '\'')
        PRINT_ERROR[code] = value

    return(HMS_ERROR, HMS_AMS_ERROR, PRINT_ERROR)



def main():
    """The true main function."""
    bambu_json_url = 'https://e.bambulab.com/query.php?lang=en'

    script_path = os.path.dirname(__file__)

    json_data = download_json_data(bambu_json_url)

    HMS_ERROR, HMS_AMS_ERROR, PRINT_ERROR = process_json(json_data)

    with open(f"{script_path}/../custom_components/bambu_lab/pybambu/const_hms_errors.py", 'w') as file:
        file.write("HMS_ERRORS = {\n")
        for key in sorted(HMS_ERROR):
            file.write(f"    \"{key}\": \"{HMS_ERROR[key]}\",\n")
        file.write("}\n")
    with open(f"{script_path}/../custom_components/bambu_lab/pybambu/const_ams_errors.py", 'w') as file:
        file.write("HMS_AMS_ERRORS = {\n")
        for key in sorted(HMS_AMS_ERROR):
            file.write(f"    \"{key}\": \"{HMS_AMS_ERROR[key]}\",\n")
        file.write("}\n")
    with open(f"{script_path}/../custom_components/bambu_lab/pybambu/const_print_errors.py", 'w') as file:
        file.write("PRINT_ERROR_ERRORS = {\n")
        for key in sorted(PRINT_ERROR):
            file.write(f"    \"{key}\": \"{PRINT_ERROR[key]}\",\n")
        file.write("}\n")

if __name__ == '__main__':
    main()
    exit(0)
