"""Sensor platform for PVOutput FoxESS."""
import json
import logging
from datetime import timedelta, datetime
import os
import asyncio
import aiohttp

import requests
from pymodbus.client import ModbusTcpClient
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_MODBUS_IP,
    CONF_INVERTER_TYPE,
    CONF_PVOUTPUT_API_KEY,
    CONF_PVOUTPUT_SYSTEM_ID,
    CONF_UPLOAD_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Define the keys for sensors that are sent to PVOutput
PVOUTPUT_SENSORS = [
    "solar_energy_today",
    "pv_power_now",
    "grid_consumption_energy_today",
    "load_power",
    "invtemp",
    "rvolt",
    "grid_voltage_R",
    "rvolt_R",
    "rvolt_A",
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform."""
    config = entry.data
    modbus_ip = config[CONF_MODBUS_IP]
    inverter_type = config[CONF_INVERTER_TYPE]
    upload_interval = config[CONF_UPLOAD_INTERVAL]

    # Load inverter profiles asynchronously to avoid blocking
    path = os.path.join(os.path.dirname(__file__), 'inverter_profiles.json')
    def load_profiles():
        with open(path, "r") as f:
            return json.load(f)
    inverter_profiles = await hass.async_add_executor_job(load_profiles)
    profile = inverter_profiles[inverter_type]

    # Find all dependencies for the PVOutput sensors
    required_keys = set(PVOUTPUT_SENSORS)
    
    # This loop is to make sure we also include sensors that are used in lambda calculations
    # e.g. pv_power_now might be a sum of pv1_power and pv2_power
    for _ in range(len(profile)): # Loop to catch nested dependencies
        for register in profile:
            key = register.get("key")
            if key in required_keys and register.get("type") == "lambda":
                for source in register.get("sources", []):
                    required_keys.add(source)

    coordinator = FoxESSDataCoordinator(
        hass, modbus_ip, profile, inverter_type, timedelta(minutes=upload_interval)
    )

    await coordinator.async_config_entry_first_refresh()
    
    # Immediately push data to PVOutput after first load
    if coordinator.pvoutput_uploader and coordinator.data:
        await coordinator.pvoutput_uploader.async_upload_data(coordinator.data)

    sensors = []
    for register in profile:
        key = register.get("key")
        if key in required_keys:
            sensors.append(FoxESSSensor(coordinator, key, register))

    async_add_entities(sensors)
    
    # Set up PVOutput uploader
    pvoutput_uploader = PVOutputUploader(hass, config, coordinator)
    hass.data[DOMAIN][entry.entry_id]["pvoutput_uploader"] = pvoutput_uploader

    # Pass the uploader to the coordinator so it can trigger uploads
    coordinator.set_pvoutput_uploader(pvoutput_uploader)

    pvoutput_status_sensors = [
        PVOutputLastUploadSensor(pvoutput_uploader),
        PVOutputLastStatusSensor(pvoutput_uploader),
    ]
    async_add_entities(pvoutput_status_sensors)

    # Let the uploader know about the sensors so it can trigger updates
    pvoutput_uploader.set_status_sensors(pvoutput_status_sensors)

    # Now that the uploader exists, set up the button platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["button"])
    )


class FoxESSDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass, modbus_ip, profile, inverter_type, update_interval):
        """Initialize."""
        self.modbus_ip = modbus_ip
        self.profile = profile
        self.inverter_type = inverter_type
        self.pvoutput_uploader = None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    def set_pvoutput_uploader(self, uploader):
        """Set the PVOutput uploader instance."""
        self.pvoutput_uploader = uploader

    async def _async_update_data(self):
        """Fetch data from the inverter."""
        try:
            data = await self.hass.async_add_executor_job(self._read_modbus_data)
            if data and self.pvoutput_uploader:
                await self.pvoutput_uploader.async_upload_data(data)
            return data
        except Exception as e:
            raise UpdateFailed(f"Error communicating with inverter: {e}")

    def _read_modbus_data(self):
        """Read data from Modbus."""
        client = ModbusTcpClient(self.modbus_ip, port=502)
        data = {}
        try:
            if not client.connect():
                _LOGGER.error("Failed to connect to inverter")
                return {}

            for register in self.profile:
                if register.get('type') == 'sensor':
                    key = register['key']
                    try:
                        address = register['addresses'][0]
                        count = len(register['addresses'])
                        result = client.read_holding_registers(address, count=count, slave=247)
                        
                        if not result.isError():
                            if count > 1:
                                value = (result.registers[0] << 16) + result.registers[1]
                            else:
                                value = result.registers[0]

                            if register.get('signed'):
                                bit_length = 16 * count
                                if value & (1 << (bit_length - 1)):
                                    value -= (1 << bit_length)

                            if 'scale' in register and register['scale'] is not None:
                                value = value * register['scale']
                            
                            data[key] = value
                        else:
                            _LOGGER.warning(f"Error reading {register['name']} ({key}): {result}")

                    except Exception as e:
                        _LOGGER.error(f"Error reading {register['name']} ({key}): {e}")

            # Calculate lambda values
            for register in self.profile:
                if register.get('type') == 'lambda':
                    key = register['key']
                    try:
                        sources = [data.get(source_key) for source_key in register['sources']]
                        if all(s is not None for s in sources):
                            data[key] = sum(s for s in sources if s is not None)
                    except Exception as e:
                         _LOGGER.error(f"Error calculating {register['name']} ({key}): {e}")
            
            return data

        finally:
            if client.is_socket_open():
                client.close()


class FoxESSSensor(Entity):
    """Representation of a FoxESS sensor."""

    def __init__(self, coordinator: FoxESSDataCoordinator, key: str, register_info: dict):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._key = key
        self._register_info = register_info
        self._name = register_info.get("name", key)

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.modbus_ip)},
            "name": f"FoxESS {self.coordinator.modbus_ip}",
            "manufacturer": "FoxESS",
            "model": self.coordinator.inverter_type,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.coordinator.modbus_ip}-{self._key}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"FoxESS {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            value = self.coordinator.data.get(self._key)
            if value is None:
                return None
            # Show power in kW (raw value from coordinator), rounded to 1 decimal place
            if "power" in self._key and isinstance(value, (int, float)):
                return round(value, 1)
            if isinstance(value, float):
                return round(value, 2)
            return value
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if "power" in self._key:
            return "kW"
        if "energy" in self._key:
            return UnitOfEnergy.KILO_WATT_HOUR
        if "volt" in self._key:
            return UnitOfElectricPotential.VOLT
        if "temp" in self._key:
            return UnitOfTemperature.CELSIUS
        return None

    @property
    def device_class(self):
        """Return the device class."""
        if "power" in self._key:
            return SensorDeviceClass.POWER
        if "energy" in self._key:
            return SensorDeviceClass.ENERGY
        if "volt" in self._key:
            return SensorDeviceClass.VOLTAGE
        if "temp" in self._key:
            return SensorDeviceClass.TEMPERATURE
        return None

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class PVOutputUploader:
    """Handles uploading data to PVOutput."""
    
    def __init__(self, hass: HomeAssistant, config: dict, coordinator: FoxESSDataCoordinator):
        """Initialize the uploader."""
        self._hass = hass
        self._api_key = config.get(CONF_PVOUTPUT_API_KEY, "").strip()
        self._system_id = config.get(CONF_PVOUTPUT_SYSTEM_ID, "").strip()
        self._coordinator = coordinator
        self._url = "https://pvoutput.org/service/r2/addstatus.jsp"
        self.last_success_timestamp = None
        self.last_status_code = None
        self._status_sensors = []
        
        # The coordinator will now trigger the upload, so we don't need a listener here.

    def set_status_sensors(self, sensors):
        """Register sensors to receive updates."""
        self._status_sensors = sensors

    async def async_upload_data(self, data: dict | None = None):
        """Upload data to PVOutput. If data is not provided, it uses the latest from the coordinator."""
        if data is None:
            data = self._coordinator.data
        
        if not data:
            return

        required_keys = ['solar_energy_today', 'pv_power_now', 'grid_consumption_energy_today', 'load_power']
        if not all(k in data for k in required_keys):
            _LOGGER.warning("Missing required data for PVOutput upload. Skipping.")
            return

        grid_voltage = data.get('rvolt')
        if grid_voltage is None:
            grid_voltage = data.get('grid_voltage_R', data.get('rvolt_R', data.get('rvolt_A')))

        payload = {
            'd': datetime.now().strftime('%Y%m%d'),
            't': datetime.now().strftime('%H:%M'),
            'v1': int(data['solar_energy_today'] * 1000),
            'v2': int(data['pv_power_now'] * 1000),
            'v3': int(data['grid_consumption_energy_today'] * 1000),
            'v4': int(data['load_power'] * 1000),
        }
        if data.get('invtemp') is not None:
            payload['v5'] = data['invtemp']
        if grid_voltage is not None:
            payload['v6'] = grid_voltage

        headers = {
            "X-Pvoutput-Apikey": self._api_key,
            "X-Pvoutput-SystemId": self._system_id,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Don't upload if key/system_id is missing
        if not self._api_key or not self._system_id:
            _LOGGER.debug("PVOutput API Key or System ID is not configured, skipping upload.")
            return

        websession = async_get_clientsession(self._hass)
        try:
            async with websession.post(self._url, headers=headers, data=payload, timeout=10) as response:
                response_text = await response.text()
                self.last_status_code = response.status
                if response.status == 200:
                    _LOGGER.info(f"Successfully uploaded to PVOutput. Response: {response_text}")
                    self.last_success_timestamp = datetime.now().isoformat()
                else:
                    _LOGGER.warning(f"Failed to upload to PVOutput. Status: {response.status}, Response: {response_text}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Error uploading to PVOutput: {e}")
            self.last_status_code = "Error"
        
        # Manually update state of our status sensors
        for sensor in self._status_sensors:
            sensor.async_schedule_update_ha_state()


class PVOutputStatusSensorBase(Entity):
    """Base class for PVOutput status sensors."""

    _attr_should_poll = False

    def __init__(self, uploader: PVOutputUploader):
        """Initialize the sensor."""
        self._uploader = uploader
        self._coordinator = uploader._coordinator

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._coordinator.modbus_ip)},
            "name": f"FoxESS {self._coordinator.modbus_ip}",
            "manufacturer": "FoxESS",
            "model": self._coordinator.inverter_type,
        }
    
    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success


class PVOutputLastUploadSensor(PVOutputStatusSensorBase):
    """Representation of a PVOutput last upload sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "PVOutput Last Successful Upload"

    def __init__(self, uploader: PVOutputUploader):
        """Initialize the sensor."""
        super().__init__(uploader)
        self._attr_unique_id = f"{self._coordinator.modbus_ip}-pvoutput_last_upload"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._uploader.last_success_timestamp


class PVOutputLastStatusSensor(PVOutputStatusSensorBase):
    """Representation of a PVOutput last status sensor."""

    _attr_icon = "mdi:cloud-check-outline"
    _attr_name = "PVOutput Last Upload Status"

    def __init__(self, uploader: PVOutputUploader):
        """Initialize the sensor."""
        super().__init__(uploader)
        self._attr_unique_id = f"{self._coordinator.modbus_ip}-pvoutput_last_status"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._uploader.last_status_code 