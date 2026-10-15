# SPDX-License-Identifier: AGPL-3.0-only
"""Shared options/repair workflow for operator-owned signing credentials."""
from __future__ import annotations

from pathlib import Path

import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    BooleanSelector, FileSelector, FileSelectorConfig,
)

from .const import DOMAIN
from .pybambu.signing_store import (
    CredentialImportError, import_credentials, inspect_credentials, signing_directory,
)


class SigningFlowMixin:
    """A flow owns only the selected entry's signing option, never cloud auth."""

    def _signing_directory(self) -> Path:
        return signing_directory(self.hass.config.path(".storage"), self._config_entry.data["serial"])

    def _signing_supported(self) -> bool:
        # Broader models need their own hardware/firmware evidence.
        return self._config_entry.data.get("device_type", "").upper() == "X1C"

    async def _signing_status(self) -> dict:
        return await self.hass.async_add_executor_job(inspect_credentials, self._signing_directory())

    async def async_step_signed_fans(self, user_input=None):
        status = await self._signing_status()
        actions = ["signing_import", "signing_retry", "signing_disable"]
        if not self._signing_supported():
            actions = ["signing_disable"]
        return self.async_show_menu(
            step_id="signed_fans",
            menu_options=actions,
            description_placeholders={
                "status": "valid" if status["configured"] else status["reason"].replace("_", " "),
                "expires": status.get("valid_until") or "—",
                "enabled": str(self._config_entry.options.get("enable_signed_fans") is True),
            },
        )

    async def async_step_signing_import(self, user_input=None):
        if not self._signing_supported():
            return self.async_abort(reason="signing_unsupported")
        errors = {}
        if user_input is not None:
            def consume_upload():
                # Both reading and cleanup belong on the executor, including on
                # invalid archives or declined consent. Never save the upload ID.
                with process_uploaded_file(self.hass, user_input["credential_bundle"]) as path:
                    if user_input.get("consent") is not True:
                        raise CredentialImportError("signing_consent_required")
                    return import_credentials(path, self._signing_directory())

            try:
                await self.hass.async_add_executor_job(consume_upload)
            except CredentialImportError as error:
                errors["base"] = str(error)
            except (OSError, ValueError, KeyError):
                errors["base"] = "signing_invalid_archive"
            else:
                return await self._finish_signing(True)
        return self.async_show_form(
            step_id="signing_import",
            data_schema=vol.Schema({
                vol.Required("credential_bundle"): FileSelector(FileSelectorConfig(accept=".zip")),
                vol.Required("consent", default=False): BooleanSelector(),
            }),
            errors=errors,
        )

    async def async_step_signing_retry(self, user_input=None):
        if not self._signing_supported():
            return self.async_abort(reason="signing_unsupported")
        errors = {}
        if user_input is not None:
            status = await self._signing_status()
            if not status["configured"] or status["crl_stale"]:
                errors["base"] = "signing_credentials_rejected"
            elif user_input.get("consent") is not True:
                errors["base"] = "signing_consent_required"
            else:
                return await self._finish_signing(True)
        return self.async_show_form(
            step_id="signing_retry",
            data_schema=vol.Schema({vol.Required("consent", default=False): BooleanSelector()}),
            errors=errors,
        )

    async def async_step_signing_disable(self, user_input=None):
        if user_input is not None:
            return await self._finish_signing(False)
        return self.async_show_form(step_id="signing_disable", data_schema=vol.Schema({}))

    async def _finish_signing(self, enabled: bool):
        # Copy at commit time: preserve concurrent usage/auth/connection updates.
        options = dict(self._config_entry.options)
        options["enable_signed_fans"] = enabled
        self.hass.config_entries.async_update_entry(self._config_entry, options=options)
        if not enabled:
            ir.async_delete_issue(self.hass, DOMAIN, f"signing_{self._config_entry.entry_id}")
        # Only re-establish certificate provisioning; never send/replay fan commands.
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        return self.async_create_entry(title="", data=None)
