"""Light platform: power + brightness for a Gemstone controller."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
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
    entities: list[LightEntity] = [
        GemstoneLight(coord) for coord in entry.runtime_data.coordinators
    ]
    async_add_entities(entities)


class GemstoneLight(GemstoneEntity, LightEntity):
    """A Gemstone controller exposed as a light: on/off + brightness."""

    _attr_name = None  # use the device name itself
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator: GemstoneCoordinator) -> None:
        super().__init__(coordinator, "light")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return data.on_state if data is not None else None

    @property
    def brightness(self) -> int | None:
        data = self.coordinator.data
        if data is None or data.pattern is None:
            return None
        return max(0, min(255, int(data.pattern.brightness)))

    async def async_turn_on(self, **kwargs: Any) -> None:
        device = self.coordinator.device

        target_brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            target_brightness = max(0, min(255, int(kwargs[ATTR_BRIGHTNESS])))

        data = self.coordinator.data
        new_on_state: bool | None = None
        new_pattern: Pattern | None = None

        if not (data and data.on_state):
            await device.turn_on()
            new_on_state = True

        if target_brightness is not None and data and data.pattern is not None:
            current = int(data.pattern.brightness)
            if current != target_brightness:
                new_pattern = _pattern_with_brightness(data.pattern, target_brightness)
                await device.play_pattern(new_pattern)

        # Optimistic local update: avoid polling the cloud immediately, since
        # the device hasn't acknowledged the command yet and the cloud's
        # ``currentlyPlaying`` endpoint will return stale state for ~30-60s.
        # Publishing the expected state here keeps the UI in sync until the
        # next scheduled poll reconciles.
        if data is not None and (new_on_state is not None or new_pattern is not None):
            self.coordinator.async_set_updated_data(
                replace(
                    data,
                    on_state=new_on_state if new_on_state is not None else data.on_state,
                    pattern=new_pattern if new_pattern is not None else data.pattern,
                )
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        data = self.coordinator.data
        if data is not None and not data.on_state:
            return
        await self.coordinator.device.turn_off()
        # Optimistic local update — see ``async_turn_on`` for why we don't
        # refresh from the cloud immediately after issuing a command.
        if data is not None:
            self.coordinator.async_set_updated_data(replace(data, on_state=False))


def _pattern_with_brightness(pattern: Pattern, brightness: int) -> Pattern:
    """Return a copy of ``pattern`` with ``brightness`` overridden.

    The Pattern model's ``raw`` dict is the source of truth on the wire
    (``to_api`` echoes it verbatim), so we deepcopy + mutate it to
    preserve any unknown fields the device cares about.
    """
    raw = copy.deepcopy(pattern.raw) if pattern.raw else {}
    raw["brightness"] = brightness
    if not raw:
        raw = pattern.to_api()
        raw["brightness"] = brightness
    return Pattern.from_api(raw)
