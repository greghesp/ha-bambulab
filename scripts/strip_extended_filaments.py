# Example data 
#{
#    "success": true,
#    "data": [
#        {
#            "id": "BlomX0ePeK9whagJOu6u",
#            "features": [],
#            "link": "https://store.bambulab.com/products/pla-marble",
#            "name": "Bambu PLA Marble",
#            "manufacturer": "Bambu Lab",
#            "manufacturer_id": "GFA07",
#            "material": "PLA",
#            "sub_material": "PLA Marble",
#            "base_diameter": 1.75,
#            "base_min_nozzle_temp": 190,
#            "base_max_nozzle_temp": 230,
#            "base_min_bed_temp": 35,
#            "base_max_bed_temp": 45,
#            "base_density": 1.22,
#            "base_weight": 1000,
#            "notes": "",
#            "variants": [
#                {
#                    "id": "HElhPMX2fvVfbd4JxC5Q",
#                    "color_name": "red granite",
#                    "product_type": "filament with spool",
#                    "weight": 1000,
#                    "price": {
#                        "GBP": 22.99,
#                        "USD": 24.99
#                    },
#                    "color_hex": "#AD4E38",
#                    "diameter": 1.75
#                },
#                {
#                    "id": "uw7aQgpacIb2QypWJ76U",
#                    "color_name": "white marble",
#                    "product_type": "filament with spool",
#                    "weight": 1000,
#                    "price": {
#                        "GBP": 22.99,
#                        "USD": 24.99
#                    },
#                    "color_hex": "#F7F3F0",
#                    "diameter": 1.75
#                }
#            ]
#        },

import json
import os

from collections import OrderedDict

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Fields to keep in the output
FIELDS_TO_KEEP = [
    'name',
    'material',
    'sub_material',
    'base_min_nozzle_temp',
    'base_max_nozzle_temp',
    'base_density'
]

def strip_json_file():
    # Read the original JSON file
    with open(f"{SCRIPT_DIR}/../custom_components/bambu_lab/pybambu/extended_filaments.json", 'r') as f:
        json_data = json.load(f)

    # Create new list with only the desired fields
    stripped_data = {}
    for filament in json_data["data"]:
        manufacturer_id = filament['manufacturer_id']
        if manufacturer_id != "":  # Only process if manufacturer_id exists
            stripped_filament = {
                field: filament.get(field) for field in FIELDS_TO_KEEP
            }
            stripped_data[manufacturer_id] = stripped_filament

    # Sort the dictionary by manufacturer_id
    sorted_data = OrderedDict(sorted(stripped_data.items()))

    # Write the stripped data to a new file
    with open(f"{SCRIPT_DIR}/../custom_components/bambu_lab/pybambu/filaments_detail.json", 'w') as f:
        json.dump(sorted_data, f, indent=2)

    # Print summary statistics
    print(f"Processed {len(sorted_data)} filaments")
    
    # Print count by material type
    material_counts = {}
    for filament in sorted_data.values():
        material = filament['material']
        material_counts[material] = material_counts.get(material, 0) + 1
    
    print("\nFilaments by material type:")
    for material, count in sorted(material_counts.items()):
        print(f"{material}: \t{count}")

strip_json_file()