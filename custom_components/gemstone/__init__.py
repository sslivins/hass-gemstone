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


@dataclass(slots=True)
class PatternCatalogue:
    """The user's saved patterns, grouped by folder.

    ``by_folder`` maps folder name -> pattern name -> Pattern (the inner
    dict de-duplicates patterns by *name within the same folder*, keeping
    first occurrence, so the select entity has unique options per folder
    even though the cloud occasionally returns near-duplicates).

    ``pattern_to_folder`` is a reverse index pattern_id -> folder name,
    used to figure out which folder the currently-playing pattern lives
    in so the folder dropdown can default to it. If a pattern appears in
    multiple folders, the first folder seen wins.
    """

    by_folder: dict[str, dict[str, Pattern]] = field(default_factory=dict)
    pattern_to_folder: dict[str, str] = field(default_factory=dict)

    @property
    def folders(self) -> list[str]:
        """Sorted list of folder names that have at least one pattern."""
        return sorted(self.by_folder.keys())

    def patterns_in(self, folder: str) -> list[str]:
        """Sorted pattern names within ``folder``."""
        return sorted(self.by_folder.get(folder, {}).keys())

    def get(self, folder: str, name: str) -> Pattern | None:
        return self.by_folder.get(folder, {}).get(name)


@dataclass
class GemstoneRuntimeData:
    """Per-config-entry runtime state."""

    client: GemstoneClient
    coordinators: list[GemstoneCoordinator]
    catalogue: PatternCatalogue = field(default_factory=PatternCatalogue)


type GemstoneConfigEntry = ConfigEntry[GemstoneRuntimeData]


async def _load_pattern_catalogue(client: GemstoneClient) -> PatternCatalogue:
    """Walk the user's folders + folder_patterns pages and group them.

    Hidden folder slots are filtered out. Folders that wind up empty
    (every pattern hidden, or no patterns at all) are dropped so they
    don't clutter the folder dropdown.
    """
    folders = await client.folders()
    folder_by_id: dict[str, str] = {
        f.folder_id: f.name for f in folders if not f.hidden and f.name
    }

    catalogue = PatternCatalogue()
    page = 1
    while True:
        items = await client.folder_patterns(page=page)
        if not items:
            break
        for fp in items:
            if fp.hidden:
                continue
            folder_name = folder_by_id.get(fp.folder_id)
            if not folder_name:
                continue
            pat = fp.pattern
            name = pat.name
            if not name:
                continue
            bucket = catalogue.by_folder.setdefault(folder_name, {})
            if name not in bucket:
                bucket[name] = pat
            if pat.id:
                catalogue.pattern_to_folder.setdefault(pat.id, folder_name)
        page += 1
    return catalogue


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
        catalogue = await _load_pattern_catalogue(client)
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
        client=client, coordinators=coordinators, catalogue=catalogue
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GemstoneConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.__aexit__(None, None, None)
    return unload_ok
