"""Select platform: pick which saved Gemstone pattern is playing."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pygemstone import Pattern

from . import GemstoneConfigEntry
from .coordinator import GemstoneCoordinator
from .entity import GemstoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GemstoneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    patterns = entry.runtime_data.patterns
    entities: list[SelectEntity] = [
        GemstonePatternSelect(coord, patterns) for coord in entry.runtime_data.coordinators
    ]
    async_add_entities(entities)


class GemstonePatternSelect(GemstoneEntity, SelectEntity):
    """Pick the active Gemstone pattern from the user's saved patterns."""

    _attr_translation_key = "pattern"
    _attr_icon = "mdi:string-lights"

    def __init__(
        self,
        coordinator: GemstoneCoordinator,
        patterns: dict[str, Pattern],
    ) -> None:
        super().__init__(coordinator, "pattern")
        self._patterns = patterns
        self._attr_options = sorted(patterns.keys())

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data is None or data.pattern is None:
            return None
        name = data.pattern.name
        return name if name in self._patterns else None

    async def async_select_option(self, option: str) -> None:
        pattern = self._patterns.get(option)
        if pattern is None:
            return
        await self.coordinator.device.play_pattern(pattern)
        # Optimistic local update: the cloud's ``currentlyPlaying`` endpoint
        # lags ~30-60s behind the device, so refreshing immediately would
        # report the previous pattern and snap the UI back. Publish the
        # expected pattern locally; the next scheduled poll reconciles.
        data = self.coordinator.data
        if data is not None:
            self.coordinator.async_set_updated_data(replace(data, pattern=pattern))
