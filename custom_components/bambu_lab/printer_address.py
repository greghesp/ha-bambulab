"""Finds a printer that moved to a new IP address."""

import asyncio
import ipaddress
from typing import Any, Mapping

from .const import LOGGER
from .pybambu import BambuClient, BambuCloud


def find_moved_printer(data: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, str] | None:
    """Return the host and access code to use for a printer that moved, or None.

    The address comes from the printer itself through Bambu Cloud, as in the config flow, and
    is only returned once the printer answers on it. Blocking: run in the executor.
    """
    if not _can_look_up(options):
        return None

    device = _get_cloud_device(data["serial"], options)
    # A printer that is off can't report its address, so don't wait for it.
    if device is None or device.get("online") is False:
        return None

    address = _get_reported_address(data, options)
    if address in ("", "0.0.0.0", options["host"]):
        return None

    access_code = device.get("dev_access_code") or options.get("access_code", "")
    LOGGER.debug(f"Printer moved from {options['host']} to {address} according to Bambu Cloud. Testing it.")
    client = BambuClient({
        "access_code": access_code,
        "device_type": data["device_type"],
        "host": address,
        "local_mqtt": True,
        "serial": data["serial"],
        "disable_ssl_verify": options.get("disable_ssl_verify", False),
    })
    # try_connection blocks, so it gets an event loop of its own rather than Home Assistant's.
    if asyncio.run(client.try_connection()) != 0:
        return None
    return {"host": address, "access_code": access_code}


def _can_look_up(options: Mapping[str, Any]) -> bool:
    if options.get("auth_token", "") == "" or not options.get("local_mqtt", False):
        return False
    if options.get("force_ip", False):
        # The user chose an address other than the one the printer reports (NAT, proxy...).
        return False
    try:
        ipaddress.ip_address(options.get("host", ""))
    except ValueError:
        # A hostname follows the printer by itself.
        return False
    return True


def _get_cloud_device(serial: str, options: Mapping[str, Any]) -> dict | None:
    cloud = BambuCloud(
        options.get("region", ""),
        options.get("email", ""),
        options.get("username", ""),
        options["auth_token"])
    return next((device for device in cloud.get_device_list() or [] if device.get("dev_id") == serial), None)


def _get_reported_address(data: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    client = BambuClient({
        "region": options.get("region", ""),
        "email": options.get("email", ""),
        "username": options.get("username", ""),
        "host": "",
        "local_mqtt": False,
        "auth_token": options["auth_token"],
        "device_type": data["device_type"],
        "serial": data["serial"],
    })
    if asyncio.run(client.try_connection()) != 0:
        return ""
    return client.get_device().info.ip_address
