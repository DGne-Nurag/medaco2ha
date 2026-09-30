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

# The portal publishes readings with a delay of roughly a day, so polling
# more often than a few times per day gains nothing.
UPDATE_INTERVAL = timedelta(hours=4)

# How far back to fetch on the very first import.
INITIAL_HISTORY = timedelta(days=90)

# OBIS codes for the registers the portal reports.
OBIS_CONSUMPTION = "1.8.0"
OBIS_FEED_IN = "2.8.0"
OBIS_NAMES = {
    OBIS_CONSUMPTION: "Bezug",
    OBIS_FEED_IN: "Einspeisung",
}
