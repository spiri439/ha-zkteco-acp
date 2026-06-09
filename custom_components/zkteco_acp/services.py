"""Home Assistant services for full control of the ZKTeco access panel."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DEFAULT_OPEN_DURATION, DOMAIN, MAX_OPEN_DURATION
from .coordinator import ZKAccessCoordinator

ATTR_DEVICE_ID = "device_id"
ATTR_DOOR = "door"
ATTR_AUX = "aux"
ATTR_DURATION = "duration"
ATTR_STATE = "state"
ATTR_ENABLE = "enable"
ATTR_TABLE = "table"
ATTR_FIELDS = "fields"
ATTR_PARAMS = "params"

SERVICE_OPEN_DOOR = "open_door"
SERVICE_SET_AUX_OUTPUT = "set_aux_output"
SERVICE_SET_NORMALLY_OPEN = "set_normally_open"
SERVICE_CANCEL_ALARMS = "cancel_alarms"
SERVICE_RESTART = "restart"
SERVICE_SYNC_DATETIME = "sync_datetime"
SERVICE_GET_USERS = "get_users"
SERVICE_GET_DATA = "get_data"
SERVICE_GET_PARAMS = "get_params"

_DEVICE_FIELD = {vol.Required(ATTR_DEVICE_ID): vol.Any(cv.string, [cv.string])}

OPEN_DOOR_SCHEMA = vol.Schema(
    {
        **_DEVICE_FIELD,
        vol.Required(ATTR_DOOR): vol.All(int, vol.Range(min=1)),
        vol.Optional(ATTR_DURATION, default=DEFAULT_OPEN_DURATION): vol.All(
            int, vol.Range(min=1, max=MAX_OPEN_DURATION)
        ),
    }
)
SET_AUX_OUTPUT_SCHEMA = vol.Schema(
    {
        **_DEVICE_FIELD,
        vol.Required(ATTR_AUX): vol.All(int, vol.Range(min=1)),
        vol.Required(ATTR_STATE): cv.boolean,
    }
)
SET_NORMALLY_OPEN_SCHEMA = vol.Schema(
    {
        **_DEVICE_FIELD,
        vol.Required(ATTR_DOOR): vol.All(int, vol.Range(min=1)),
        vol.Required(ATTR_ENABLE): cv.boolean,
    }
)
DEVICE_ONLY_SCHEMA = vol.Schema({**_DEVICE_FIELD})
GET_DATA_SCHEMA = vol.Schema(
    {
        **_DEVICE_FIELD,
        vol.Required(ATTR_TABLE): cv.string,
        vol.Optional(ATTR_FIELDS): vol.All(cv.ensure_list, [cv.string]),
    }
)
GET_PARAMS_SCHEMA = vol.Schema(
    {
        **_DEVICE_FIELD,
        vol.Required(ATTR_PARAMS): vol.All(cv.ensure_list, [cv.string]),
    }
)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> ZKAccessCoordinator:
    """Resolve the target panel coordinator from a device_id."""
    device_ids = call.data[ATTR_DEVICE_ID]
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    registry = dr.async_get(hass)
    store: dict = hass.data.get(DOMAIN, {})
    for device_id in device_ids:
        device = registry.async_get(device_id)
        if not device:
            continue
        for entry_id in device.config_entries:
            if entry_id in store:
                return store[entry_id]
    raise HomeAssistantError(
        f"No ZKTeco access panel found for device_id={device_ids}"
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_OPEN_DOOR):
        return

    async def open_door(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_open_door(
            call.data[ATTR_DOOR], call.data[ATTR_DURATION]
        )

    async def set_aux_output(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_set_aux_output(
            call.data[ATTR_AUX], call.data[ATTR_STATE]
        )

    async def set_normally_open(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_set_normal_open(
            call.data[ATTR_DOOR], call.data[ATTR_ENABLE]
        )

    async def cancel_alarms(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_cancel_alarms()

    async def restart(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_restart()

    async def sync_datetime(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_sync_datetime()

    async def get_users(call: ServiceCall) -> ServiceResponse:
        users = await _coordinator(hass, call).async_get_data("user")
        return {"users": users, "count": len(users)}

    async def get_data(call: ServiceCall) -> ServiceResponse:
        rows = await _coordinator(hass, call).async_get_data(
            call.data[ATTR_TABLE], call.data.get(ATTR_FIELDS)
        )
        return {"rows": rows, "count": len(rows)}

    async def get_params(call: ServiceCall) -> ServiceResponse:
        return await _coordinator(hass, call).async_get_params(call.data[ATTR_PARAMS])

    hass.services.async_register(DOMAIN, SERVICE_OPEN_DOOR, open_door, OPEN_DOOR_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_AUX_OUTPUT, set_aux_output, SET_AUX_OUTPUT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_NORMALLY_OPEN, set_normally_open, SET_NORMALLY_OPEN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_ALARMS, cancel_alarms, DEVICE_ONLY_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RESTART, restart, DEVICE_ONLY_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_DATETIME, sync_datetime, DEVICE_ONLY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_USERS,
        get_users,
        DEVICE_ONLY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DATA,
        get_data,
        GET_DATA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PARAMS,
        get_params,
        GET_PARAMS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove integration services."""
    for service in (
        SERVICE_OPEN_DOOR,
        SERVICE_SET_AUX_OUTPUT,
        SERVICE_SET_NORMALLY_OPEN,
        SERVICE_CANCEL_ALARMS,
        SERVICE_RESTART,
        SERVICE_SYNC_DATETIME,
        SERVICE_GET_USERS,
        SERVICE_GET_DATA,
        SERVICE_GET_PARAMS,
    ):
        hass.services.async_remove(DOMAIN, service)
