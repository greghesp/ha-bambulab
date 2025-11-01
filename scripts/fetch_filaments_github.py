"""
Script to fetch filament data from Bambu Lab's GitHub repository and save it to a JSON file.
"""

import aiohttp
import asyncio
import json
import os

from collections import OrderedDict
from pathlib import Path

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Fields to keep in the output
FIELDS_TO_KEEP = [
    'name',
    'filament_vendor',
    'filament_type',
    'filament_density',
    'nozzle_temperature',
    'nozzle_temperature_range_high',
    'nozzle_temperature_range_low',
]

def resolve_inherited_value(name: str, field: str, raw_data: dict[str, any]) -> any:
    """
    Recursively resolve a field value by following the inheritance chain.
    
    Args:
        name: Name of the current filament profile
        field: Field to resolve
        raw_data: Dictionary of all filament profiles
    
    Returns:
        The resolved value or None if not found
    """
    
    # Get the current profile
    profile = raw_data.get(name)
    if not profile:
        return None
    
    # Check if the field exists in current profile
    value = profile.get(field)
    if value is not None:
        return value
    
    # If not found, check the inherited profile
    inherits = profile.get('inherits')
    if inherits:
        return resolve_inherited_value(inherits, field, raw_data)
    
    return None

def sanitize_field(field, value):
    if isinstance(value, list):
        value = value[0]

    if value is None:
        return None
        
    # Add specific field processing logic
    if field == 'name':
        return value.split(' @')[0]
    if field in ['filament_cost', 'filament_density']:
        return float(value)
    elif field in ['nozzle_temperature', 'nozzle_temperature_range_high', 'nozzle_temperature_range_low']:
        return int(value)

    return value

async def fetch_filaments():
    """
    Fetches filament data from Bambu Lab's GitHub repository and saves it to filament.json
    """
    base_url = "https://api.github.com/repos/bambulab/BambuStudio/contents/resources/profiles/BBL/filament"
    stripped_data = {}
    raw_data = {}

    try:
        print(f"Fetching filament IDs from: {base_url}")
        
        async with aiohttp.ClientSession() as session:
            # First fetch the directory listing
            async with session.get(base_url) as response:
                files = await response.json()

            # First pass: Load all raw data
            for file in files:
                if file['name'].endswith('.json'):
                    # Skip files with '@' that aren't '@base'
                    if ' @' in file['name'] and not ' @base' in file['name']:
                        continue
                    print(f"Fetching {file['name']}")
                    async with session.get(file['download_url']) as content_response:
                        content = await content_response.text()
                        content = json.loads(content)
                        
                        # Store by name for easy lookup
                        if 'name' in content:
                            raw_data[content['name']] = content

            # Second pass: Process and resolve inherited values
            for name, content in raw_data.items():
                if 'filament_id' in content:
                    # Resolve all required fields through inheritance chain
                    stripped_filament = {}
                    for field in FIELDS_TO_KEEP:
                        value = resolve_inherited_value(name, field, raw_data)
                        value = sanitize_field(field, value)
                        if isinstance(value, list) and value:
                            value = value[0]  # Take first element if it's a list
                        stripped_filament[field] = sanitize_field(field, value)                   
                    stripped_data[content['filament_id']] = stripped_filament
                elif 'setting_id' in content:
                    # Resolve all required fields through inheritance chain
                    stripped_filament = {}
                    for field in FIELDS_TO_KEEP:
                        value = resolve_inherited_value(name, field, raw_data)
                        if isinstance(value, list) and value:
                            value = value[0]  # Take first element if it's a list
                        stripped_filament[field] = sanitize_field(field, value)
                    
                    stripped_data[content['setting_id']] = stripped_filament

        # Sort the dictionary by manufacturer_id
        sorted_data = OrderedDict(sorted(stripped_data.items()))

        # Write the data to filaments_github.json
        with open(f"{SCRIPT_DIR}/../custom_components/bambu_lab/filaments_github.json", 'w') as f:
            json.dump(raw_data, f, indent=2)

        # Write the data to filaments_detail.json
        with open(f"{SCRIPT_DIR}/../custom_components/bambu_lab/filaments_detail.json", 'w') as f:
            json.dump(sorted_data, f, indent=2)
        
        print("Successfully wrote filament data to filament.json")

    except Exception as error:
        print(f"Error fetching filament IDs: {error}")

asyncio.run(fetch_filaments())