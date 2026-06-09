"""Binary sensors for the ZKTeco ACP integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZKAccessCoordinator
from .entity import ZKAccessEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for doors, alarms, aux inputs and connectivity."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]
    info = coordinator.info

    entities: list[BinarySensorEntity] = [ZKAccessConnectivity(coordinator)]
    for door in range(1, info.nr_of_locks + 1):
        entities.append(ZKAccessLockStatus(coordinator, door))
        entities.append(ZKAccessDoorSensor(coordinator, door))
        entities.append(ZKAccessDoorAlarm(coordinator, door))
    for aux in range(1, info.nr_aux_in + 1):
        entities.append(ZKAccessAuxInput(coordinator, aux))

    async_add_entities(entities)


class ZKAccessConnectivity(ZKAccessEntity, BinarySensorEntity):
    """Whether the last poll reached the panel."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connectivity"

    def __init__(self, coordinator: ZKAccessCoordinator) -> None:
        super().__init__(coordinator, "connectivity")

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def available(self) -> bool:
        return True


class ZKAccessLockStatus(ZKAccessEntity, BinarySensorEntity):
    """Lock status (relay): on = unlocked/released, off = locked/armed.

    Derived from hold-open state and momentary relay pulses (the panel does not
    report the relay back). Defaults to locked, so it is never 'unknown'.
    """

    _attr_device_class = BinarySensorDeviceClass.LOCK
    _attr_translation_key = "door_lock"

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}_lock")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @property
    def is_on(self) -> bool:
        # device_class LOCK: on == unlocked. locks[door]: True == released.
        return bool(self.coordinator.data.locks.get(self._door, False))


class ZKAccessDoorSensor(ZKAccessEntity, BinarySensorEntity):
    """Physical door open/closed (the reed/magnetic contact)."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_translation_key = "door"

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.doors.get(self._door)


class ZKAccessDoorAlarm(ZKAccessEntity, BinarySensorEntity):
    """Alarm state for a door (forced open, open too long…)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "door_alarm"

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}_alarm")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.door_alarms.get(self._door))

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        return {"alarms": self.coordinator.data.door_alarms.get(self._door, [])}


class ZKAccessAuxInput(ZKAccessEntity, BinarySensorEntity):
    """Auxiliary input (exit button, door contact, sensor…)."""

    _attr_translation_key = "aux_input"

    def __init__(self, coordinator: ZKAccessCoordinator, aux: int) -> None:
        super().__init__(coordinator, f"aux_in_{aux}")
        self._aux = aux
        self._attr_translation_placeholders = {"aux": str(aux)}

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.aux_in.get(self._aux)
