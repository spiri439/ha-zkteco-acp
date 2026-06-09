"""Sensors for the ZKTeco ACP integration — last realtime event details."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ZKAccessCoordinator
from .entity import ZKAccessEntity


@dataclass(frozen=True, kw_only=True)
class ZKAccessSensorDescription(SensorEntityDescription):
    """Describes a ZKTeco ACP sensor, reading from the last_event dict."""

    value_fn: Callable[[dict[str, Any] | None], Any]


def _ts(event: dict[str, Any] | None) -> Any:
    if not event or not event.get("timestamp"):
        return None
    return dt_util.parse_datetime(event["timestamp"])


SENSORS: tuple[ZKAccessSensorDescription, ...] = (
    ZKAccessSensorDescription(
        key="last_event_type",
        translation_key="last_event_type",
        icon="mdi:account-key",
        value_fn=lambda e: e.get("event_type") if e else None,
    ),
    ZKAccessSensorDescription(
        key="last_event_card",
        translation_key="last_event_card",
        icon="mdi:card-account-details",
        value_fn=lambda e: (e.get("card_no") if e else None) or None,
    ),
    ZKAccessSensorDescription(
        key="last_event_door",
        translation_key="last_event_door",
        icon="mdi:door",
        value_fn=lambda e: e.get("door") if e else None,
    ),
    ZKAccessSensorDescription(
        key="last_event_time",
        translation_key="last_event_time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_ts,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZKTeco ACP sensors."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [ZKAccessSensor(coordinator, desc) for desc in SENSORS]
    entities.append(ZKAccessUsersSensor(coordinator))
    async_add_entities(entities)


class ZKAccessSensor(ZKAccessEntity, SensorEntity):
    """Reports a field from the most recent realtime event."""

    entity_description: ZKAccessSensorDescription

    def __init__(
        self, coordinator: ZKAccessCoordinator, description: ZKAccessSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data.last_event)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self.coordinator.data.last_event
        if not event:
            return {}
        return {
            "direction": event.get("direction"),
            "verified": event.get("verified"),
            "pin": event.get("pin"),
        }


class ZKAccessUsersSensor(ZKAccessEntity, SensorEntity):
    """Number of users enrolled on the panel."""

    _attr_translation_key = "users"
    _attr_icon = "mdi:account-group"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZKAccessCoordinator) -> None:
        super().__init__(coordinator, "users")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.users_count
