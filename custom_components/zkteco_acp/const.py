"""Constants for the ZKTeco Access Control Panel integration."""

from __future__ import annotations

DOMAIN = "zkteco_acp"
MANUFACTURER = "ZKTeco"

# Config / options keys
CONF_OPEN_DURATION = "open_duration"

# Defaults
DEFAULT_PORT = 4370
DEFAULT_PASSWORD = ""
DEFAULT_SCAN_INTERVAL = 3  # seconds — short, this is a real-time event stream
MIN_SCAN_INTERVAL = 1
DEFAULT_OPEN_DURATION = 5  # seconds a door relay stays released on "open"
MAX_OPEN_DURATION = 254  # 255 == continuous (handled as "normally open")

# Bus event fired for every realtime access event (card swipe, granted/denied…)
EVENT_ACCESS = f"{DOMAIN}_event"
