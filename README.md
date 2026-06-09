<img src="brands/zkteco_acp/icon.png" width="96" align="right" alt="ZKTeco ACP icon" />

# ZKTeco Access Control Panel — Home Assistant integration

[![Validate](https://github.com/spiri439/ha-zkteco-acp/actions/workflows/validate.yml/badge.svg)](https://github.com/spiri439/ha-zkteco-acp/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration for **ZKTeco access-control panels** of the
**C3 / inBio / ACP / Atlas** family (e.g. **ACP-200**, C3-100/200/400). Built on
the pure-Python [`zkaccess-c3`](https://github.com/vwout/zkaccess-c3-py) library,
so it runs anywhere Home Assistant runs (no Windows DLL).

> **Important:** access-control *panels* use a different protocol from ZKTeco
> *attendance terminals*. `pyzk` does **not** work with these panels — this
> integration uses the C3 "PULL SDK" protocol on TCP port `4370`.

Validated against an **ACP-200** (serial `ORO61…`, firmware `AC Ver 4.3.3`,
2 doors / 2 aux-in / 2 aux-out).

## Entities

For a 2-door panel you get:

**Buttons**
- Open door 1 / 2 — momentary release (duration configurable)
- Cancel alarms
- Restart panel

**Locks** (one per door — the padlock visual)
- Door 1 / 2 lock — **lock** = secure, **unlock** = hold open (normally-open),
  **open** = momentary buzz-in. State is optimistic (panel doesn't report the
  relay back).

**Switches**
- Aux output 1 / 2 — relay on/off

**Binary sensors**
- Door 1 / 2 (the magnetic/reed contact — open/closed; needs a wired door sensor)
- Door 1 / 2 alarm (forced open / open-too-long…)
- Aux input 1 / 2
- Connectivity

**Sensors**
- Last event / last event card / last event door / last event time
- Users (number of enrolled users/cards)

**Buttons (extra)**
- Sync time — set the panel clock to Home Assistant's time

**Event entities** — one per door (`event.door_1_access_event`, …) that fires on
every realtime access event (card presented, access granted/denied, exit button,
door opened, etc.).

## Realtime events for automations

Every realtime event also fires a `zkteco_acp_event` bus event:

```yaml
automation:
  - alias: "Notify on access at door 1"
    trigger:
      - platform: event
        event_type: zkteco_acp_event
        event_data:
          door: 1
    action:
      - service: notify.notify
        data:
          message: >
            Door 1: {{ trigger.event.data.event_type }}
            (card {{ trigger.event.data.card_no }},
            {{ trigger.event.data.direction }})
```

Event data: `host`, `door`, `card_no`, `pin`, `event_type`, `event_name`,
`event_code`, `direction`, `verified`, `timestamp`.

Or use the per-door **event entity** as a trigger (recommended):

```yaml
    trigger:
      - platform: state
        entity_id: event.door_1_access_event
```

## Services (full control)

All actions are also exposed as services, targetable by device:

| Service | What it does |
|---|---|
| `zkteco_acp.open_door` | Release a door (`door`, optional `duration`) |
| `zkteco_acp.set_aux_output` | Switch an aux output relay (`aux`, `state`) |
| `zkteco_acp.set_normally_open` | Hold a door open / release hold (`door`, `enable`) |
| `zkteco_acp.cancel_alarms` | Clear active alarms |
| `zkteco_acp.restart` | Reboot the panel |
| `zkteco_acp.sync_datetime` | Set panel clock to HA time |
| `zkteco_acp.get_users` | Return the user/card table (response) |
| `zkteco_acp.get_data` | Read any data table — `user`, `transaction`, `timezone`, `holiday`… (response) |
| `zkteco_acp.get_params` | Read device parameters by name (response) |

Example — read all users:

```yaml
action: zkteco_acp.get_users
target:
  device_id: <panel device id>
response_variable: result
# result.users -> list of card/user rows, result.count -> total
```

> **Note:** the underlying `zkaccess-c3` library is **read + control** — it can read
> users/cards/transactions and drive doors/relays/alarms/time, but cannot *write*
> the user table (no card enrolment over this protocol). Card enrolment is done on
> the panel / ZKAccess software.

## HACS install (recommended)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/spiri439/ha-zkteco-acp`
   as category **Integration**.
2. Install **ZKTeco Access Control Panel**, restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → "ZKTeco Access Control Panel"**.
4. Enter IP (`10.10.0.62`), port (`4370`), and leave the password empty unless a
   communication password is set on the panel.

## Manual install

1. Copy `custom_components/zkteco_acp` into your HA `config/custom_components/`.
2. Restart Home Assistant, then add the integration as above.

## Test connectivity first (recommended)

```bash
pip install zkaccess-c3
python3 test_connection.py 10.10.0.62 4370
```

If it prints the serial/firmware and (optionally) realtime events, the
integration will work.

## Dashboard

A ready-made Lovelace dashboard (doors, controls, status, and a door-event
logbook) is provided in [`examples/lovelace-dashboard.yaml`](examples/lovelace-dashboard.yaml).
Adjust the `entity_id`s to match your device, then add it as a new dashboard in
YAML mode.

## How it works / design notes

- **One persistent TCP connection** is held open and `get_rt_log()` is polled on
  a short interval (default **3s**). The C3 realtime log is an event stream, so a
  persistent connection avoids missing events (unlike attendance terminals where
  reconnect-per-poll is fine).
- The `c3` library is synchronous and its socket is not thread-safe, so all
  device I/O runs in HA's executor and is serialised through a lock — door-open
  buttons can't collide with the poll loop.
- On any I/O error the connection is dropped and re-established next cycle;
  `binary_sensor.connectivity` reflects this.
- Door open duration is sent to the panel, which times the relay itself.

## Networking notes (from setup of the validated panel)

- The panel answers ICMP ping and accepts TCP `4370`. Earlier failures were a
  VPN path issue; the C3 protocol traverses TCP `4370` once the route is up.
- Wrong library was the original red herring: `pyzk` connects the TCP socket but
  the panel never replies, because it isn't the attendance protocol.

## Two visuals per door

Each physical door is a *lock relay* **and** a *reed/magnetic contact*. They show
as two entities:

- **`lock.…door_1_lock`** — padlock icon: locked / unlocked (relay)
- **`binary_sensor.…door_1`** — door icon: closed / open (magnetic contact)

The example dashboard places them side by side as tiles.

## Brand icon

The icon lives in [`brands/zkteco_acp/`](brands/zkteco_acp/) (`icon.png` 256×256,
`icon@2x.png` 512×512, `logo.png`), generated by
[`tools/make_icon.py`](tools/make_icon.py).

Home Assistant only loads integration icons from the central
[`home-assistant/brands`](https://github.com/home-assistant/brands) repository, not
from a custom repo. To make the icon appear in the HA UI, open a PR there adding
these files under `custom_integrations/zkteco_acp/`. Until then HA shows a default
icon — the integration works regardless.

## Limitations / ideas

- Lock state is optimistic (the panel doesn't report relay / normal-open state back).
- User/card management (enrolling cards, time zones) is not implemented yet — the
  `zkaccess-c3` library exposes `get_device_data` / data tables that a future
  version could use.
