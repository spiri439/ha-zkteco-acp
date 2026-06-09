"""Config flow for the ZKTeco ACP integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from c3 import C3

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_OPEN_DURATION,
    DEFAULT_OPEN_DURATION,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_OPEN_DURATION,
    MIN_SCAN_INTERVAL,
)


def _validate_sync(data: dict[str, Any]) -> dict[str, str]:
    """Blocking connection test. Returns serial number + device name."""
    dev = C3(data[CONF_HOST], data.get(CONF_PORT, DEFAULT_PORT))
    if not dev.connect(data.get(CONF_PASSWORD) or None):
        raise CannotConnect("connect() returned False")
    try:
        return {
            "serial": dev.serial_number or data[CONF_HOST],
            "name": dev.device_name or "",
        }
    finally:
        dev.disconnect()


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    try:
        return await hass.async_add_executor_job(_validate_sync, data)
    except CannotConnect:
        raise
    except Exception as err:  # noqa: BLE001
        raise CannotConnect(str(err)) from err


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL)),
            vol.Optional(
                CONF_OPEN_DURATION, default=d.get(CONF_OPEN_DURATION, DEFAULT_OPEN_DURATION)
            ): vol.All(int, vol.Range(min=1, max=MAX_OPEN_DURATION)),
        }
    )


class ZKAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZKTeco ACP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                result = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(result["serial"])
                self._abort_if_unique_id_configured()
                name = result["name"] or user_input[CONF_HOST]
                return self.async_create_entry(
                    title=f"ZKTeco ACP {name}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ZKAccessOptionsFlow()


class ZKAccessOptionsFlow(OptionsFlow):
    """Tune scan interval and door-open duration after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        data = self.config_entry.data
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(
                        CONF_SCAN_INTERVAL,
                        data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_OPEN_DURATION,
                    default=opts.get(
                        CONF_OPEN_DURATION,
                        data.get(CONF_OPEN_DURATION, DEFAULT_OPEN_DURATION),
                    ),
                ): vol.All(int, vol.Range(min=1, max=MAX_OPEN_DURATION)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
