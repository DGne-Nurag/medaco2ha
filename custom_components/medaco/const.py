"""Constants for the Westnetz MeDaCo integration."""

from datetime import timedelta

DOMAIN = "medaco"

CONF_PORTAL = "portal"

# Both network operators run the same MeDaCo portal software.
PORTALS = {
    "westnetz": "https://medaco.westnetz.de",
    "westenergie": "https://medaco.westenergie.de",
}
DEFAULT_PORTAL = "westnetz"

# Smart meter gateways deliver 15 minute values to the portal within minutes.
UPDATE_INTERVAL = timedelta(minutes=15)

# How far back to fetch on the very first import, and the size of each
# request while catching up.
INITIAL_HISTORY = timedelta(days=365)
FETCH_CHUNK = timedelta(days=31)

# OBIS codes of the 15 minute energy registers (1.29.0 = Bezug, 2.29.0 =
# Einspeisung) the portal reports for an intelligent metering system.
OBIS_CONSUMPTION = "1-1:1.29.0"
OBIS_FEED_IN = "1-1:2.29.0"
OBIS_NAMES = {
    OBIS_CONSUMPTION: "Bezug",
    OBIS_FEED_IN: "Einspeisung",
}
