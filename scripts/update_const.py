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
    """Downlaod the JSON from Bambu"""
    req = urllib.request.Request(json_url, headers={'User-Agent' : "Magic Browser"}) 
    con = urllib.request.urlopen(req)
    return(con.read())
    

def open_const(file_to_read, unique_id_start, unique_id_end):
    """Open the file and return data before and after the unique ID"""
    file_handler = open(file_to_read, "r")
    location = 0
    text_before_unique_id = ""
    text_after_unique_id = ""
    for line in file_handler.readlines():
        if location == 0:
            text_before_unique_id += line
            if unique_id_start in line:
                location = 1
        if location == 1:
            if unique_id_end in line:
                text_after_unique_id += line
                location = 2
                continue  # We must continue otherwise we get double this line
        if location == 2:
            text_after_unique_id += line
    #print(text_before_unique_id, end='')
    #print("JSON DATA GOES HERE")
    #print(text_after_unique_id, end='')
    file_handler.close()
    return(text_before_unique_id, text_after_unique_id)


def write_new_file(file_to_write, file_contents):
    """Write the new const.py file"""
    file_handler = open(file_to_write, "w")
    file_handler.write(file_contents)
    file_handler.close()
    return


def process_json(json_data):
    """Process the JSON data and prep it for adding to const.py"""
    bambu_data = json.loads(json_data)
    HMS_ERROR_text = ""
    HMS_AMS_ERROR_text = ""
    PRINT_ERROR_text = ""
    for error_entry in bambu_data['data']['device_hms']['en']:
        # Check if this is an AMS error code, they start with 070
        if error_entry['ecode'].startswith('070'):
            # Format is (including 4 spaces at the front)
            #   "WWWW_XXXX_YYYY_ZZZZ": "text",
            # Use the replace at the end because some of the fields have double quotes in them, just replace with single quotes
            HMS_AMS_ERROR_text += "    \"" + error_entry['ecode'][slice(0,4,1)].upper() + "_" + error_entry['ecode'][slice(4,8,1)].upper() + "_" + error_entry['ecode'][slice(8,12,1)].upper() + "_" + error_entry['ecode'][slice(12,16,1)].upper() + "\": \"" + error_entry['intro'].replace('\"', '\'') + "\",\n"
        else:
            HMS_ERROR_text += "    \"" + error_entry['ecode'][slice(0,4,1)].upper() + "_" + error_entry['ecode'][slice(4,8,1)].upper() + "_" + error_entry['ecode'][slice(8,12,1)].upper() + "_" + error_entry['ecode'][slice(12,16,1)].upper() + "\": \"" + error_entry['intro'].replace('\"', '\'') + "\",\n"
    for error_entry in bambu_data['data']['device_error']['en']:
        PRINT_ERROR_text += "    \"" + error_entry['ecode'][slice(0,4,1)].upper() + "_" + error_entry['ecode'][slice(4,8,1)].upper() + "\": \"" + error_entry['intro'].replace('\"', '\'') + "\",\n"
    #print(json.dumps(error_entry, indent=4))
    #print(HMS_AMS_ERROR_text, end='')
    #print(HMS_ERROR_text, end='')
    #print(PRINT_ERROR_text, end='')
    return(HMS_AMS_ERROR_text, HMS_ERROR_text, PRINT_ERROR_text)



def main():
    """The true main function."""
    bambu_json_url = 'https://e.bambulab.com/query.php?lang=en'
    const_py_file_location = '../custom_components/bambu_lab/pybambu/const.py'
    HMS_ERROR_unique_id_start = 'dAa5VFRi'
    HMS_ERROR_unique_id_end = 'wy2WtJ2q'
    HMS_AMS_ERROR_unique_id_start = 'dxeWW5n6'
    HMS_AMS_ERROR_unique_id_end = 'ARxX6kr9'
    PRINT_ERROR_unique_id_start = 'ZEJTS2b8'
    PRINT_ERROR_unique_id_end = 'Y329g6Nq'

    check_for_file(const_py_file_location)
    json_data = download_json_data(bambu_json_url)
    HMS_AMS_ERROR_text, HMS_ERROR_text, PRINT_ERROR_text = process_json(json_data)
    hms_section_before_text, hms_section_after_text = open_const(const_py_file_location, HMS_ERROR_unique_id_start, HMS_ERROR_unique_id_end)
    write_new_file(const_py_file_location, hms_section_before_text + "HMS_ERRORS = {\n" + HMS_ERROR_text + "}\n" + hms_section_after_text)
    hms_ams_section_before_text, hms_ams_section_after_text = open_const(const_py_file_location, HMS_AMS_ERROR_unique_id_start, HMS_AMS_ERROR_unique_id_end)
    write_new_file(const_py_file_location, hms_ams_section_before_text + "HMS_AMS_ERRORS = {\n" + HMS_AMS_ERROR_text + "}\n" + hms_ams_section_after_text)
    print_section_before_text, print_section_after_text = open_const(const_py_file_location, PRINT_ERROR_unique_id_start, PRINT_ERROR_unique_id_end)
    write_new_file(const_py_file_location, print_section_before_text + "PRINT_ERROR_ERRORS = {\n" + PRINT_ERROR_text + "}\n" + print_section_after_text)




if __name__ == '__main__':
    main()
    exit(0)
