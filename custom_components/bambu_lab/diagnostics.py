"""Diagnostics support for Bambu Lab integration."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BambuDataUpdateCoordinator
from .pybambu.commands import PUSH_ALL, GET_VERSION
from .pybambu.const import Features


TO_REDACT = [
    "access_code",
    "auth_token",
    "email",
    "serial",
    "sn",
    "title",
    "username",
    "cover",
    "deviceId",
    "modelId"
]


def serialize_pybambu_object(obj: Any) -> Any:
    """Recursively serialize pybambu objects to JSON-serializable format."""
    
    if obj is None:
        return None
    
    # Handle basic types
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle lists
    if isinstance(obj, list):
        return [serialize_pybambu_object(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: serialize_pybambu_object(value) for key, value in obj.items()}
    
    # Handle binary data types
    if isinstance(obj, (bytes, bytearray)):
        return {"type": "binary_data", "size_bytes": len(obj)}
    
    # Handle pybambu objects (classes with __dict__)
    if hasattr(obj, '__dict__'):
        result = {}
        
        # Include all attributes from __dict__
        for key, value in obj.__dict__.items():
            # Skip client references, binary data, and MQTT data that's captured separately
            if key not in ['_client', '_bytes', 'push_all_data', 'get_version_data']:
                try:
                    if isinstance(value, (bytes, bytearray)):
                        result[key] = {"type": "binary_data", "size_bytes": len(value)}
                    else:
                        serialized_value = serialize_pybambu_object(value)
                        if serialized_value is not None:
                            result[key] = serialized_value
                except Exception as e:
                    # If serialization fails, just skip this attribute
                    pass
        
        return result
    
    # Handle other objects
    try:
        return str(obj)
    except:
        return None


async def async_get_config_entry_diagnostics(
        hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return comprehensive diagnostics for a config entry.
    
    This includes:
    - Configuration entry data (redacted)
    - Raw MQTT data (push_all and get_version) (redacted)
    - Class member state from pybambu objects (redacted)
    - Feature support information
    """
    
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Must convert this to a dict for redaction to work correctly. Redaction leaves empty values as empty so we know if a value was present or not.
    entry = coordinator.config_entry.as_dict()

    coordinator.client.publish(PUSH_ALL)
    coordinator.client.publish(GET_VERSION)

    # Get the device object
    device = coordinator.get_model()
    
    # Serialize the entire device state
    try:
        device_state = serialize_pybambu_object(device)
    except Exception as e:
        device_state = {"error": f"Exception during serialization: {str(e)}"}
    
    # Get feature support information
    feature_support = {}
    if device:
        for feature in Features:
            try:
                feature_support[feature.name] = device.supports_feature(feature)
            except Exception as e:
                pass

    return {
        "config_entry": async_redact_data(entry, TO_REDACT),
        "pushall": {
            "print": async_redact_data(coordinator.data.push_all_data, TO_REDACT)
        },
        "get_version": {
            "info": async_redact_data(coordinator.data.get_version_data, TO_REDACT)
        },
        "device_state": async_redact_data(device_state, TO_REDACT),
        "feature_support": feature_support,
    }
