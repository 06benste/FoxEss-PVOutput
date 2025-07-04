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
import aiohttp
import asyncio
from pymodbus.client import ModbusTcpClient

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

    async def _validate_modbus_ip(self, ip: str) -> bool:
        """Try to connect to the inverter via Modbus TCP."""
        def try_connect():
            client = ModbusTcpClient(ip, port=502)
            try:
                return client.connect()
            finally:
                if client.is_socket_open():
                    client.close()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, try_connect)

    async def _validate_pvoutput_credentials(self, api_key: str, system_id: str) -> bool:
        """Check PVOutput API key and system ID by calling getstatus.jsp."""
        url = "https://pvoutput.org/service/r2/getstatus.jsp"
        headers = {
            "X-Pvoutput-Apikey": api_key,
            "X-Pvoutput-SystemId": system_id,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    return resp.status == 200
        except Exception as e:
            _LOGGER.error(f"PVOutput credential check failed: {e}")
            return False

    async def _fetch_pvoutput_system_name(self, api_key: str, system_id: str) -> str | None:
        """Fetch the PVOutput system name using the API key and system ID."""
        url = "https://pvoutput.org/service/r2/getsystem.jsp"
        headers = {
            "X-Pvoutput-Apikey": api_key,
            "X-Pvoutput-SystemId": system_id,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # CSV: systemName,...
                        parts = text.split(",")
                        if len(parts) > 0:
                            return parts[0].strip()
        except Exception as e:
            _LOGGER.error(f"Failed to fetch PVOutput system name: {e}")
        return None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            # Validate Modbus IP
            valid_ip = await self._validate_modbus_ip(user_input[CONF_MODBUS_IP])
            if not valid_ip:
                errors[CONF_MODBUS_IP] = "cannot_connect"
            if not errors:
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
            api_key = self.data.get(CONF_PVOUTPUT_API_KEY, "").strip()
            system_id = self.data.get(CONF_PVOUTPUT_SYSTEM_ID, "").strip()
            if api_key and system_id:
                valid = await self._validate_pvoutput_credentials(api_key, system_id)
                if not valid:
                    errors[CONF_PVOUTPUT_API_KEY] = "invalid_api_key_or_system_id"
                    errors[CONF_PVOUTPUT_SYSTEM_ID] = "invalid_api_key_or_system_id"
            if not errors:
                # Try to fetch the PVOutput system name
                system_name = None
                if api_key and system_id:
                    system_name = await self._fetch_pvoutput_system_name(api_key, system_id)
                title = f"{system_name} - PV Output" if system_name else f"{self.data[CONF_MODBUS_IP]} - PV Output"
                return self.async_create_entry(title=title, data=self.data)

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