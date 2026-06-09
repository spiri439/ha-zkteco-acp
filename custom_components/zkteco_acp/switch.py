"""Switches for the ZKTeco ACP integration: auxiliary output relays.

Door hold-open is handled by the door ``lock`` entities (unlock == hold open),
so it is intentionally not duplicated here.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up aux-output switches."""
    coordinator: ZKAccessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZKAccessAuxOutput(coordinator, aux)
        for aux in range(1, coordinator.info.nr_aux_out + 1)
    )


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
