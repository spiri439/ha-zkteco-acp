"""Base entity for the ZKTeco ACP integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ZKAccessCoordinator


class ZKAccessEntity(CoordinatorEntity[ZKAccessCoordinator]):
    """Base entity tying everything to the panel device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZKAccessCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        info = self.coordinator.info
        identifier = info.serial_number or self.coordinator.entry.entry_id
        connections = {("mac", info.mac)} if info.mac and info.mac != "?" else set()
        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=MANUFACTURER,
            name=(
                info.device_name
                if info.device_name and info.device_name != "?"
                else f"ZKTeco ACP {self.coordinator.host}"
            ),
            model=info.firmware_version,
            sw_version=info.firmware_version,
            serial_number=info.serial_number,
            connections=connections,
        )
