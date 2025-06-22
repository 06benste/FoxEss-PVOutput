"""Config flow for PVOutput FoxESS integration."""
import json
import logging
from typing import Any, Dict
import os

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_MODBUS_IP,
    CONF_INVERTER_TYPE,
    CONF_PVOUTPUT_API_KEY,
    CONF_PVOUTPUT_SYSTEM_ID,
    CONF_UPLOAD_INTERVAL,
    DEFAULT_UPLOAD_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

def get_inverter_types():
    """Load inverter types from the JSON file."""
    try:
        path = os.path.join(os.path.dirname(__file__), 'inverter_profiles.json')
        with open(path, "r") as f:
            return list(json.load(f).keys())
    except (FileNotFoundError, json.JSONDecodeError):
        return ["AC1", "H1_G2", "H3_PRO"] # Fallback

INVERTER_TYPES = get_inverter_types()

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PVOutput FoxESS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            # Here you would typically validate the input, e.g., try to connect to the inverter
            # For simplicity, we'll just assume it's correct
            self.data = user_input
            return await self.async_step_pvoutput()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MODBUS_IP): cv.string,
                vol.Required(CONF_INVERTER_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=INVERTER_TYPES, mode=selector.SelectSelectorMode.DROPDOWN),
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )

    async def async_step_pvoutput(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Handle the PVOutput configuration step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            self.data.update(user_input)
            
            # You could add validation for the API key here if desired
            
            return self.async_create_entry(title=self.data[CONF_MODBUS_IP], data=self.data)

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_PVOUTPUT_API_KEY): cv.string,
                vol.Optional(CONF_PVOUTPUT_SYSTEM_ID): cv.string,
                vol.Required(CONF_UPLOAD_INTERVAL, default=DEFAULT_UPLOAD_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )
        
        return self.async_show_form(
            step_id="pvoutput",
            data_schema=data_schema,
            errors=errors
        ) 