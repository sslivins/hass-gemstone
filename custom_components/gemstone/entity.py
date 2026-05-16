"""Base entity for the Gemstone Lights integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import GemstoneCoordinator


class GemstoneEntity(CoordinatorEntity[GemstoneCoordinator]):
    """Common base for all Gemstone entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GemstoneCoordinator,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=device.name,
            sw_version=device.firmware,
            serial_number=device.id,
        )
