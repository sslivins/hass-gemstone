"""Config flow for Gemstone Lights."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pygemstone import (
    GemstoneAuthError,
    GemstoneClient,
    GemstoneConnectionError,
    GemstoneError,
)

from .const import DOMAIN

USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


class GemstoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gemstone Lights."""

    VERSION = 1

    async def _validate(self, email: str, password: str) -> str | None:
        """Try to log in. Returns an error key on failure, None on success."""
        client = GemstoneClient(email=email, password=password)
        await client.__aenter__()
        try:
            await client.login()
        except GemstoneAuthError:
            return "invalid_auth"
        except GemstoneConnectionError:
            return "cannot_connect"
        except GemstoneError:
            return "unknown"
        finally:
            await client.__aexit__(None, None, None)
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            err = await self._validate(email, user_input[CONF_PASSWORD])
            if err is None:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            errors["base"] = err
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            email = entry.data[CONF_EMAIL]
            err = await self._validate(email, user_input[CONF_PASSWORD])
            if err is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            errors["base"] = err
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
        )
