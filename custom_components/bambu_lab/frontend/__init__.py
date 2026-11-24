"""Frontend for Bambu Lab Cards"""

import asyncio
import logging
import os
import pathlib

from packaging.version import parse

from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import __version__

from ..pybambu.utils import (
    compare_version,
)

from ..const import BAMBU_LAB_CARDS, URL_BASE, LOGGER

_LOGGER = logging.getLogger(__name__)


def find_external_card_resources(resources, filename: str) -> list:
    """Return Lovelace resources that load ``filename`` from outside URL_BASE.

    A separately installed copy of the cards (e.g. the standalone HACS
    frontend repo served from /hacsfiles/ha-bambulab-cards/) defines the same
    custom elements as the bundled copy. Loading both makes the browser throw
    "the name ... has already been used with this registry".
    """
    external = []
    for resource in resources:
        path = str(resource.get("url", "")).split("?")[0]
        if path.startswith(URL_BASE):
            continue
        if path.rsplit("/", 1)[-1] == filename:
            external.append(resource)
    return external


class BambuLabCardRegistration:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def lovelace_resource_mode(self):
        if compare_version(__version__, "2026.2.0") >= 0:
            return self.hass.data["lovelace"].resource_mode
        elif compare_version(__version__, "2025.2.0") >= 0:
            return self.hass.data["lovelace"].mode
        else:
            return self.hass.data["lovelace"]["mode"]

    @property
    def lovelace_resources(self):
        if compare_version(__version__, "2025.2.0") >= 0:
            return self.hass.data["lovelace"].resources
        else:
            return self.hass.data["lovelace"]["resources"]

    async def async_register(self):
        """Serve the cards and add them to the Lovelace resources.

        The printer works without the cards, so a failure here is only logged.
        """
        try:
            await self.async_register_bambu_path()
            if self.lovelace_resource_mode == "storage":
                await self.async_load_lovelace_resources()
                await self.async_register_bambu_cards()
            else:
                _LOGGER.debug(
                    "Not installing Bambu Cards because Lovelace resources are in %s mode",
                    self.lovelace_resource_mode,
                )
        except Exception:
            _LOGGER.exception("Failed to register the Bambu Lab cards")

    # install card 
    async def async_register_bambu_path(self):
        """Register custom cards path if not already registered"""
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, pathlib.Path(__file__).parent, False)]
            )
            _LOGGER.debug("Registered Bambu Lab path from %s", pathlib.Path(__file__).parent)
        except RuntimeError:
            _LOGGER.debug("Bambu Lab static path already registered")


    async def async_load_lovelace_resources(self) -> None:
        """Load the resources now instead of waiting for a browser to do it.

        Home Assistant only loads them when the first dashboard asks for the list.
        Waiting for that gives that dashboard the list from before the cards were
        added or updated, and it doesn't ask again until the page is reloaded.
        """
        if self.lovelace_resources.loaded:
            return
        await self.lovelace_resources.async_get_info()
        # A dashboard that asked while we were loading shares our read, but stores its
        # result after us. Let it finish so that it doesn't undo what we change next.
        await asyncio.sleep(0)

    async def async_register_bambu_cards(self):
        _LOGGER.debug("Installing Lovelace resource for Bambu Cards")

        # Get resources already registered
        bambu_resources = [
            resource
            for resource in self.lovelace_resources.async_items()
            if resource["url"].startswith(URL_BASE)
        ]

        all_resources = list(self.lovelace_resources.async_items())

        for card in BAMBU_LAB_CARDS:
            url = f"{URL_BASE}/{card.get('filename')}"

            external = find_external_card_resources(all_resources, card.get("filename"))
            if external:
                _LOGGER.warning(
                    "%s is already loaded from %s. Skipping the copy bundled with the "
                    "integration to avoid loading the cards twice. Remove that resource "
                    "(and the separate HACS frontend install) to use the bundled cards.",
                    card.get("name"),
                    ", ".join(str(res.get("url")) for res in external),
                )
                for res in bambu_resources:
                    if self.get_resource_path(res["url"]) == url:
                        await self.lovelace_resources.async_delete_item(res.get("id"))
                continue

            card_registered = False

            for res in bambu_resources:
                if self.get_resource_path(res["url"]) == url:
                    card_registered = True
                    #check version
                    if self.get_resource_version(res["url"]) != card.get("version"):

                        # Update card version
                        _LOGGER.debug("Updating %s to version %s", card.get("name"), card.get("version"))
                        await self.lovelace_resources.async_update_item(res.get("id"), {
                            "res_type":"module",
                            "url":url + "?v=" + card.get("version")
                        })

                        # Remove old gzipped files
                        await self.async_remove_gzip_files()
                    else:
                        _LOGGER.debug("%s already registered as version %s", card.get("name"), card.get("version"))

            if not card_registered:
                _LOGGER.debug("Registering %s as version %s", card.get("name"), card.get("version"))
                await self.lovelace_resources.async_create_item({
                    "res_type":"module",
                    "url":url + "?v=" + card.get("version")
                })

    def get_resource_path(self, url: str):
        return url.split("?")[0]
    
    def get_resource_version(self, url: str):
        try:
            return url.split("?")[1].replace("v=", "")
        except Exception:
            return 0
        

    async def async_unregister(self):
        # Unload lovelace module resource
        if self.lovelace_resource_mode == "storage":
            await self.async_load_lovelace_resources()
            for card in BAMBU_LAB_CARDS:
                url = f"{URL_BASE}/{card.get('filename')}"
                bambu_resources = [
                    resource
                     for resource in self.lovelace_resources.async_items()
                    if str(resource["url"]).startswith(url)
                ]

                for resource in bambu_resources:
                    await self.lovelace_resources.async_delete_item(resource.get("id"))

    async def async_remove_gzip_files(self):
        await self.hass.async_add_executor_job(self.remove_gzip_files)

    def remove_gzip_files(self):
        _LOGGER.debug("remove_gzip_files")
        path = self.hass.config.path("custom_components/bambu_lab/frontend")

        gzip_files = [
            filename for filename in os.listdir(path) if filename.endswith(".gz")
        ]

        _LOGGER.debug(gzip_files)
        for file in gzip_files:
            try:
                if os.path.getmtime(f"{path}/{file}") < os.path.getmtime(f"{path}/{file.replace('.gz','')}"):
                    _LOGGER.debug(f"Removing older gzip file - {file}")
                    os.remove(f"{path}/{file}")
            except Exception:
                pass