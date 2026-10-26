"""The Westnetz MeDaCo integration."""

from __future__ import annotations

from homeassistant.components.recorder import get_instance
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MedacoClient
from .const import CONF_PORTAL, DEFAULT_PORTAL, DOMAIN, PORTALS
from .coordinator import MedacoCoordinator

PLATFORMS = [Platform.SENSOR]
SERVICE_REIMPORT = "reimport"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MedacoConfigEntry = ConfigEntry[MedacoCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the service that rebuilds the imported history."""

    async def reimport(call: ServiceCall) -> None:
        recorder = get_instance(hass)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            coordinator: MedacoCoordinator = entry.runtime_data
            recorder.async_clear_statistics(list(coordinator.data))
            await recorder.async_block_till_done()
            await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, SERVICE_REIMPORT, reimport)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MedacoConfigEntry) -> bool:
    """Set up MeDaCo from a config entry."""
    client = MedacoClient(
        # Own session so portal cookies don't leak into other integrations.
        async_create_clientsession(hass),
        PORTALS[entry.data.get(CONF_PORTAL, DEFAULT_PORTAL)],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = MedacoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MedacoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
