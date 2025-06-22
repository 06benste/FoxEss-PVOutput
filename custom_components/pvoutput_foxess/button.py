"""Button platform for PVOutput FoxESS."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensor import PVOutputUploader

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    uploader = hass.data[DOMAIN][entry.entry_id].get("pvoutput_uploader")
    if uploader:
        async_add_entities([PVOutputPushButton(uploader)])


class PVOutputPushButton(ButtonEntity):
    """Representation of a PVOutput push button."""

    _attr_icon = "mdi:cloud-upload-outline"

    def __init__(self, uploader: PVOutputUploader) -> None:
        """Initialize the button."""
        self._uploader = uploader
        self._coordinator = uploader._coordinator
        self._attr_name = f"Push to PVOutput"
        self._attr_unique_id = f"{self._coordinator.modbus_ip}-push_to_pvoutput"

    @property
    def device_info(self):
        """Return device information to link the button to the correct device."""
        return {
            "identifiers": {(DOMAIN, self._coordinator.modbus_ip)},
            "name": f"FoxESS {self._coordinator.modbus_ip}",
            "manufacturer": "FoxESS",
            "model": self._coordinator.inverter_type,
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._uploader.async_upload_data() 