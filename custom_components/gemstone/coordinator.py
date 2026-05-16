"""DataUpdateCoordinator for Gemstone devices."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pygemstone import (
    Device,
    DeviceState,
    GemstoneAuthError,
    GemstoneConnectionError,
    GemstoneError,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GemstoneCoordinator(DataUpdateCoordinator[DeviceState]):
    """Polling coordinator for a single Gemstone controller.

    One coordinator per device; the integration creates one for each
    Gemstone device discovered on the account at setup time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: Device,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {device.id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.device = device

    async def _async_update_data(self) -> DeviceState:
        try:
            return await self.device.refresh()
        except GemstoneAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GemstoneConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except GemstoneError as err:
            raise UpdateFailed(str(err)) from err
