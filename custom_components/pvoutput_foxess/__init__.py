"""The PVOutput FoxESS integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PVOutput FoxESS from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store an empty dictionary for this config entry.
    hass.data[DOMAIN][entry.entry_id] = {}

    # Forward the setup to the sensor platform. The sensor platform will set up the button platform.
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an integration is removed.
    # It should clean up everything created in async_setup_entry
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR, Platform.BUTTON])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok 