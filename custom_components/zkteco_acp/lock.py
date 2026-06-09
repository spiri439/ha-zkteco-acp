"""Lock entities for the ZKTeco ACP integration — one per door.

Gives a padlock visual per door. Mapping to the panel's real capabilities:

  * **lock**   -> disable normally-open (secure the door)
  * **unlock** -> enable normally-open (hold the door released)
  * **open**   -> momentary relay pulse to grant a single entry

State is derived from the **door reed/magnetic contact** (the door sensor the
panel reports in every realtime status record): door closed -> locked, door open
-> unlocked. This is a real, live signal, so it is correct after a Home Assistant
restart (unlike an optimistic guess). It reads ``unknown`` until a reed contact is
wired and the door's sensor type (``DoorNSensorType``) is set to NO/NC on the
panel.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
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
    """Set up one lock entity per door."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZKAccessDoorLock(coordinator, door)
        for door in range(1, coordinator.info.nr_of_locks + 1)
    )


class ZKAccessDoorLock(ZKAccessEntity, LockEntity):
    """A door lock backed by the panel's relay / normally-open state."""

    _attr_translation_key = "lock"
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}_lock")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @property
    def _duration(self) -> int:
        return self.coordinator.entry.options.get(
            CONF_OPEN_DURATION,
            self.coordinator.entry.data.get(CONF_OPEN_DURATION, DEFAULT_OPEN_DURATION),
        )

    @property
    def is_locked(self) -> bool | None:
        # Derived from the reed contact: door closed -> locked, open -> unlocked,
        # no signal -> unknown. doors[n]: True=open, False=closed, None=unknown.
        door_open = self.coordinator.data.doors.get(self._door)
        if door_open is None:
            return None
        return not door_open

    async def async_lock(self, **kwargs: Any) -> None:
        """Secure the door (disable normally-open)."""
        await self.coordinator.async_set_normal_open(self._door, False)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Hold the door released (enable normally-open)."""
        await self.coordinator.async_set_normal_open(self._door, True)

    async def async_open(self, **kwargs: Any) -> None:
        """Momentarily release the lock to grant a single entry."""
        await self.coordinator.async_open_door(self._door, self._duration)
