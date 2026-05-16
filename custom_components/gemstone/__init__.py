"""The Gemstone Lights integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pygemstone import (
    Device,
    GemstoneAuthError,
    GemstoneClient,
    GemstoneConnectionError,
    GemstoneError,
    Pattern,
)

from .const import PLATFORMS
from .coordinator import GemstoneCoordinator


@dataclass
class GemstoneRuntimeData:
    """Per-config-entry runtime state."""

    client: GemstoneClient
    coordinators: list[GemstoneCoordinator]
    patterns: dict[str, Pattern] = field(default_factory=dict)


type GemstoneConfigEntry = ConfigEntry[GemstoneRuntimeData]


async def _load_pattern_catalogue(client: GemstoneClient) -> dict[str, Pattern]:
    """Walk the user's saved-pattern pages and return a name->Pattern map.

    Duplicate names (same pattern in multiple folders) keep the first
    occurrence so the select entity has unique options.
    """
    patterns: dict[str, Pattern] = {}
    page = 1
    while True:
        items = await client.folder_patterns(page=page)
        if not items:
            break
        for fp in items:
            name = fp.pattern.name
            if name and name not in patterns:
                patterns[name] = fp.pattern
        page += 1
    return patterns


async def async_setup_entry(hass: HomeAssistant, entry: GemstoneConfigEntry) -> bool:
    """Set up Gemstone Lights from a config entry."""
    client = GemstoneClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    await client.__aenter__()

    try:
        await client.login()
        homegroups = await client.homegroups()
        devices: list[Device] = []
        for hg in homegroups:
            devices.extend(await client.devices(hg.id))
        patterns = await _load_pattern_catalogue(client)
    except GemstoneAuthError as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryAuthFailed(str(err)) from err
    except (GemstoneConnectionError, GemstoneError) as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryNotReady(str(err)) from err

    if not devices:
        await client.__aexit__(None, None, None)
        raise ConfigEntryNotReady("No Gemstone devices found on this account")

    coordinators: list[GemstoneCoordinator] = []
    for dev in devices:
        coord = GemstoneCoordinator(hass, entry, dev)
        await coord.async_config_entry_first_refresh()
        coordinators.append(coord)

    entry.runtime_data = GemstoneRuntimeData(
        client=client, coordinators=coordinators, patterns=patterns
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GemstoneConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.__aexit__(None, None, None)
    return unload_ok
