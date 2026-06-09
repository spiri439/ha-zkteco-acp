"""Data update coordinator for the ZKTeco Access Control Panel integration.

The C3 panel exposes a realtime log (RTLog). The model is:

  * one persistent TCP connection is held open,
  * ``get_rt_log()`` is polled on a short interval and returns any records that
    occurred since the previous call,
  * the library updates its cached door / aux input / aux output status from
    those records, which we then read back for entity state,
  * ``EventRecord`` entries (card swipes, access granted/denied, exit button…)
    are turned into Home Assistant bus events and ``event`` entity triggers.

The ``c3`` library is synchronous and not thread-safe on its socket, so every
device call is serialised through ``_io_lock`` and run in the executor.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from c3 import C3, consts, controldevice, rtlog

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_ACCESS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PanelInfo:
    """Static panel information, read once after connecting."""

    serial_number: str | None = None
    firmware_version: str | None = None
    device_name: str | None = None
    mac: str | None = None
    nr_of_locks: int = 0
    nr_aux_in: int = 0
    nr_aux_out: int = 0
    ip_address: str | None = None
    netmask: str | None = None
    gateway: str | None = None


@dataclass
class PanelData:
    """Snapshot of one polling cycle."""

    # door_nr -> True(open)/False(closed)/None(unknown, e.g. no sensor)
    doors: dict[int, bool | None] = field(default_factory=dict)
    door_alarms: dict[int, list[str]] = field(default_factory=dict)
    aux_in: dict[int, bool | None] = field(default_factory=dict)
    aux_out: dict[int, bool | None] = field(default_factory=dict)
    last_event: dict[str, Any] | None = None
    new_events: list[dict[str, Any]] = field(default_factory=list)
    users_count: int | None = None


def _to_bool(status: consts.InOutStatus) -> bool | None:
    if status == consts.InOutStatus.OPEN:
        return True
    if status == consts.InOutStatus.CLOSED:
        return False
    return None


def _aware(value: Any) -> datetime | None:
    """Convert the panel's naive local timestamp to a tz-aware datetime."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.get_default_time_zone())
    return value


class ZKAccessCoordinator(DataUpdateCoordinator[PanelData]):
    """Holds the C3 connection and polls the realtime log."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._password: str = entry.data.get(CONF_PASSWORD, "") or ""

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        self._dev = C3(self.host, self.port)
        self._io_lock = threading.Lock()
        self.info = PanelInfo()
        # Persisted per-door alarm state (refreshed whenever a status record arrives).
        self._alarms: dict[int, list[str]] = {}
        # Heavier metadata (user count) is fetched roughly once a minute, not every poll.
        self._poll_count = 0
        self._meta_every = max(1, round(60 / max(1, scan_interval)))
        self._users_count: int | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {self.host}",
            update_interval=timedelta(seconds=scan_interval),
        )

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> PanelData:
        try:
            data = await self.hass.async_add_executor_job(self._poll)
        except Exception as err:  # noqa: BLE001 - any failure => unavailable this cycle
            # Drop the connection so the next cycle reconnects cleanly.
            await self.hass.async_add_executor_job(self._safe_disconnect)
            raise UpdateFailed(f"Error talking to C3 panel {self.host}: {err}") from err

        for event in data.new_events:
            self.hass.bus.async_fire(EVENT_ACCESS, event)
        return data

    def _poll(self) -> PanelData:
        with self._io_lock:
            if not self._dev.is_connected():
                self._connect_locked()

            records = self._dev.get_rt_log()
            data = PanelData()

            # Process records: alarms + realtime events.
            for rec in records:
                if isinstance(rec, rtlog.DoorAlarmStatusRecord):
                    for door in range(1, self.info.nr_of_locks + 1):
                        alarms = rec.get_alarms(door)
                        if alarms:
                            self._alarms[door] = [str(a) for a in alarms]
                        else:
                            self._alarms[door] = []
                elif isinstance(rec, rtlog.EventRecord):
                    event = self._event_to_dict(rec)
                    data.new_events.append(event)
                    data.last_event = event

            # Cached status (updated by get_rt_log above).
            for door in range(1, self.info.nr_of_locks + 1):
                data.doors[door] = _to_bool(self._dev.lock_status(door))
                data.door_alarms[door] = list(self._alarms.get(door, []))
            for aux in range(1, self.info.nr_aux_in + 1):
                data.aux_in[aux] = _to_bool(self._dev.aux_in_status(aux))
            for aux in range(1, self.info.nr_aux_out + 1):
                data.aux_out[aux] = _to_bool(self._dev.aux_out_status(aux))

            # Carry the last event forward across polls without a fresh one.
            if data.last_event is None and self.data is not None:
                data.last_event = self.data.last_event

            # Periodically refresh the (heavier) user count.
            self._poll_count += 1
            if self._poll_count == 1 or self._poll_count % self._meta_every == 0:
                try:
                    self._users_count = len(self._dev.get_device_data("user"))
                except Exception:  # noqa: BLE001 - non-fatal, keep last known
                    _LOGGER.debug("Failed to read user table", exc_info=True)
            data.users_count = self._users_count
            return data

    def _connect_locked(self) -> None:
        """Connect and (first time) read static info. Caller holds the lock."""
        if not self._dev.connect(self._password or None):
            raise ConnectionError("connect() returned False")
        if self.info.serial_number is None:
            net: dict[str, str] = {}
            try:
                net = self._dev.get_device_param(
                    ["IPAddress", "NetMask", "GATEIPAddress"]
                )
            except Exception:  # noqa: BLE001 - network params are optional
                _LOGGER.debug("Failed to read network params", exc_info=True)
            self.info = PanelInfo(
                serial_number=self._dev.serial_number,
                firmware_version=self._dev.firmware_version,
                device_name=self._dev.device_name,
                mac=self._dev.mac,
                nr_of_locks=self._dev.nr_of_locks,
                nr_aux_in=self._dev.nr_aux_in,
                nr_aux_out=self._dev.nr_aux_out,
                ip_address=net.get("IPAddress"),
                netmask=net.get("NetMask"),
                gateway=net.get("GATEIPAddress"),
            )

    def _event_to_dict(self, rec: rtlog.EventRecord) -> dict[str, Any]:
        return {
            "host": self.host,
            "card_no": rec.card_no,
            "pin": rec.pin,
            "door": rec.port_nr,
            "event_type": str(rec.event_type),
            "event_name": rec.event_type.name.lower(),
            "event_code": int(rec.event_type),
            "direction": str(rec.in_out_state),
            "verified": str(rec.verified),
            "timestamp": (
                _aware(rec.time_second).isoformat()
                if _aware(rec.time_second)
                else None
            ),
        }

    def _safe_disconnect(self) -> None:
        with self._io_lock:
            try:
                if self._dev.is_connected():
                    self._dev.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error during disconnect", exc_info=True)

    async def async_shutdown_panel(self) -> None:
        await self.hass.async_add_executor_job(self._safe_disconnect)

    # ------------------------------------------------------------------
    # Control actions (buttons / switches)
    # ------------------------------------------------------------------
    async def async_control(self, command: controldevice.ControlDeviceBase) -> None:
        """Run a control command, serialised against the poll loop."""

        def _run() -> None:
            with self._io_lock:
                if not self._dev.is_connected():
                    self._connect_locked()
                self._dev.control_device(command)

        await self.hass.async_add_executor_job(_run)
        # Refresh soon so entity state reflects the change.
        await self.async_request_refresh()

    async def async_open_door(self, door_nr: int, duration: int) -> None:
        await self.async_control(
            controldevice.ControlDeviceOutput(
                door_nr, consts.ControlOutputAddress.DOOR_OUTPUT, duration
            )
        )

    async def async_set_aux_output(self, aux_nr: int, on: bool) -> None:
        await self.async_control(
            controldevice.ControlDeviceOutput(
                aux_nr,
                consts.ControlOutputAddress.AUX_OUTPUT,
                255 if on else 0,
            )
        )

    async def async_set_normal_open(self, door_nr: int, enable: bool) -> None:
        await self.async_control(
            controldevice.ControlDeviceNormalOpenStateEnable(door_nr, enable)
        )

    async def async_cancel_alarms(self) -> None:
        await self.async_control(controldevice.ControlDeviceCancelAlarms())

    async def async_restart(self) -> None:
        await self.async_control(controldevice.ControlDeviceRestart())

    # ------------------------------------------------------------------
    # Data / parameter access (services)
    # ------------------------------------------------------------------
    async def async_get_data(
        self, table: str, fields: list[str] | None = None
    ) -> list[dict]:
        """Read a data table (e.g. 'user', 'transaction', 'timezone')."""

        def _run() -> list[dict]:
            with self._io_lock:
                if not self._dev.is_connected():
                    self._connect_locked()
                return self._dev.get_device_data(table, fields)

        return await self.hass.async_add_executor_job(_run)

    async def async_get_params(self, params: list[str]) -> dict:
        """Read device parameters by name."""

        def _run() -> dict:
            with self._io_lock:
                if not self._dev.is_connected():
                    self._connect_locked()
                return self._dev.get_device_param(params)

        return await self.hass.async_add_executor_job(_run)

    async def async_sync_datetime(self, when: datetime | None = None) -> None:
        """Set the panel clock (defaults to now)."""

        def _run() -> None:
            with self._io_lock:
                if not self._dev.is_connected():
                    self._connect_locked()
                self._dev.set_device_datetime(when)

        await self.hass.async_add_executor_job(_run)
