"""Event entities for the ZKTeco ACP integration — one per door.

Each realtime ``EventRecord`` for a door triggers the matching event entity,
exposing the card number / direction / verification mode as attributes. This is
the HA-native way to build automations ("when card X is presented at door 1").
"""

from __future__ import annotations

from c3 import consts

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZKAccessCoordinator
from .entity import ZKAccessEntity

# Stable, predefined list of event types this entity can emit.
EVENT_TYPES: list[str] = sorted({e.name.lower() for e in consts.EventType})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one access-event entity per door."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZKAccessDoorEvent(coordinator, door)
        for door in range(1, coordinator.info.nr_of_locks + 1)
    )


class ZKAccessDoorEvent(ZKAccessEntity, EventEntity):
    """Fires on every realtime access event for a single door."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_translation_key = "door_event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}_event")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}

    @callback
    def _handle_coordinator_update(self) -> None:
        for event in self.coordinator.data.new_events:
            if event.get("door") != self._door:
                continue
            event_name = event.get("event_name", "na")
            if event_name not in self._attr_event_types:
                event_name = "unknown_unsupported"
            self._trigger_event(
                event_name,
                {
                    "event_type": event.get("event_type"),
                    "card_no": event.get("card_no"),
                    "pin": event.get("pin"),
                    "direction": event.get("direction"),
                    "verified": event.get("verified"),
                    "timestamp": event.get("timestamp"),
                },
            )
        super()._handle_coordinator_update()
