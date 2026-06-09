"""Switches for the ZKTeco ACP integration: aux outputs and door hold-open."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up aux-output and door hold-open switches."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    for aux in range(1, coordinator.info.nr_aux_out + 1):
        entities.append(ZKAccessAuxOutput(coordinator, aux))
    for door in range(1, coordinator.info.nr_of_locks + 1):
        entities.append(ZKAccessDoorHoldOpen(coordinator, door))

    async_add_entities(entities)


class ZKAccessAuxOutput(ZKAccessEntity, SwitchEntity):
    """Auxiliary output relay (continuous on / off)."""

    _attr_translation_key = "aux_output"
    _attr_icon = "mdi:electric-switch"

    def __init__(self, coordinator: ZKAccessCoordinator, aux: int) -> None:
        super().__init__(coordinator, f"aux_out_{aux}")
        self._aux = aux
        self._attr_translation_placeholders = {"aux": str(aux)}

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.aux_out.get(self._aux)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_aux_output(self._aux, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_aux_output(self._aux, False)


class ZKAccessDoorHoldOpen(ZKAccessEntity, SwitchEntity):
    """Hold a door in the 'normally open' (unlocked) state.

    The panel does not report this state back, so the switch is optimistic.
    """

    _attr_translation_key = "door_hold_open"
    _attr_icon = "mdi:door-sliding-open"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZKAccessCoordinator, door: int) -> None:
        super().__init__(coordinator, f"door_{door}_hold_open")
        self._door = door
        self._attr_translation_placeholders = {"door": str(door)}
        self._attr_is_on = False

    @property
    def is_on(self) -> bool:
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_normal_open(self._door, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_normal_open(self._door, False)
        self._attr_is_on = False
        self.async_write_ha_state()
