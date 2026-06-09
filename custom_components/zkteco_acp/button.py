"""Buttons for the ZKTeco ACP integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_OPEN_DURATION, DEFAULT_OPEN_DURATION, DOMAIN
from .coordinator import ZKAccessCoordinator
from .entity import ZKAccessEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up door-open, cancel-alarm and restart buttons."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = [
        ZKAccessCancelAlarmsButton(coordinator),
        ZKAccessRestartButton(coordinator),
        ZKAccessSyncTimeButton(coordinator),
    ]
    for door in range(1, coordinator.info.nr_of_locks + 1):
        entities.append(ZKAccessOpenDoorButton(coordinator, door))

    async_add_entities(entities)


class ZKAccessOpenDoorButton(ZKAccessEntity, ButtonEntity):
    """Momentarily release a door lock to grant entry."""

    _attr_translation_key = "open_door"
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"open_door_{door}")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @property
    def _duration(self) -> int:
        return self.coordinator.entry.options.get(
            CONF_OPEN_DURATION,
            self.coordinator.entry.data.get(CONF_OPEN_DURATION, DEFAULT_OPEN_DURATION),
        )

    async def async_press(self) -> None:
        await self.coordinator.async_open_door(self._door, self._duration)


class ZKAccessCancelAlarmsButton(ZKAccessEntity, ButtonEntity):
    """Clear active alarms on the panel."""

    _attr_translation_key = "cancel_alarms"
    _attr_icon = "mdi:alarm-light-off"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZKAccessCoordinator) -> None:
        super().__init__(coordinator, "cancel_alarms")

    async def async_press(self) -> None:
        await self.coordinator.async_cancel_alarms()


class ZKAccessRestartButton(ZKAccessEntity, ButtonEntity):
    """Reboot the panel."""

    _attr_translation_key = "restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZKAccessCoordinator) -> None:
        super().__init__(coordinator, "restart")

    async def async_press(self) -> None:
        await self.coordinator.async_restart()


class ZKAccessSyncTimeButton(ZKAccessEntity, ButtonEntity):
    """Set the panel clock to Home Assistant's current time."""

    _attr_translation_key = "sync_time"
    _attr_icon = "mdi:clock-edit"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZKAccessCoordinator) -> None:
        super().__init__(coordinator, "sync_time")

    async def async_press(self) -> None:
        await self.coordinator.async_sync_datetime()
