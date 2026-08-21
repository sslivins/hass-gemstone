"""DataUpdateCoordinator for Gemstone devices."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pygemstone import (
    ArchitecturalDesign,
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

    ``active_folder`` is UI-only state shared between the folder picker
    and pattern picker entities. It's None until the user explicitly
    selects a folder, in which case the picker entities fall back to
    "the folder of the currently playing pattern" via the catalogue's
    reverse index.
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
        self.active_folder: str | None = None
        self.architectural_designs: list[ArchitecturalDesign] = []

    async def async_refresh_architectural_designs(self) -> None:
        """Fetch this device's saved "Custom Designs" (Quick Access looks).

        Best-effort: an error here shouldn't block integration setup, so
        callers should be prepared for the list to stay empty if the
        cloud call fails.
        """
        self.architectural_designs = await self.device.architectural_designs()

    def set_active_folder(self, folder: str | None) -> None:
        """Update the active folder and notify listening entities.

        The pattern picker reads ``coordinator.active_folder`` to
        decide which folder's patterns to expose; calling
        ``async_update_listeners`` re-renders both selects so the
        pattern dropdown's options switch in lockstep.
        """
        self.active_folder = folder
        self.async_update_listeners()

    async def _async_update_data(self) -> DeviceState:
        try:
            return await self.device.refresh()
        except GemstoneAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GemstoneConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except GemstoneError as err:
            raise UpdateFailed(str(err)) from err
