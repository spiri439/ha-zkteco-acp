#!/usr/bin/env python3
"""Standalone ZKTeco C3 / ACP access-panel connectivity tester.

Confirms the panel is reachable and dumps its details + a few seconds of the
realtime event stream. Does NOT require Home Assistant and performs only
READ-ONLY operations (it never opens a door or toggles a relay).

    pip install zkaccess-c3
    python3 test_connection.py 10.10.0.62 4370

NOTE: ZKTeco access-control panels (C3-100/200/400, inBio, ACP-200, Atlas…) speak
a different protocol from attendance terminals — they need the `zkaccess-c3`
library, NOT `pyzk`.
"""

from __future__ import annotations

import sys
import time

try:
    from c3 import C3, rtlog
except ImportError:
    sys.exit("zkaccess-c3 is not installed.  Run:  pip install zkaccess-c3")


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "10.10.0.62"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 4370
    password = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"Connecting to C3 panel {host}:{port} ...\n")
    dev = C3(host, port)
    if not dev.connect(password):
        print("connect() returned False — wrong password or not a C3 panel.")
        return 1

    try:
        print("*** CONNECTED ***")
        print(f"  Serial   : {dev.serial_number}")
        print(f"  Firmware : {dev.firmware_version}")
        print(f"  Name     : {dev.device_name}")
        print(f"  MAC      : {dev.mac}")
        print(f"  Doors    : {dev.nr_of_locks}")
        print(f"  Aux in   : {dev.nr_aux_in}   Aux out: {dev.nr_aux_out}")

        print("\n  Watching realtime log for 10s (present a card / open a door)...")
        seen_event = False
        for _ in range(5):
            for rec in dev.get_rt_log():
                if isinstance(rec, rtlog.EventRecord):
                    seen_event = True
                    print(
                        f"    EVENT  door={rec.port_nr} card={rec.card_no} "
                        f"type={rec.event_type} dir={rec.in_out_state} "
                        f"verify={rec.verified} @ {rec.time_second}"
                    )
            for door in range(1, dev.nr_of_locks + 1):
                print(
                    f"    door {door}: {dev.lock_status(door)!s:8}",
                    end="  " if door < dev.nr_of_locks else "\n",
                )
            time.sleep(2)
        if not seen_event:
            print("    (no card/door events occurred during the window)")
    finally:
        dev.disconnect()
    print("\nDisconnected. The Home Assistant integration will work against this panel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
