"""Constants for the PVOutput FoxESS integration."""

DOMAIN = "pvoutput_foxess"

# Config flow constants
CONF_MODBUS_IP = "modbus_ip"
CONF_INVERTER_TYPE = "inverter_type"
CONF_PVOUTPUT_API_KEY = "pvoutput_api_key"
CONF_PVOUTPUT_SYSTEM_ID = "pvoutput_system_id"
CONF_SEND_TO_PVOUTPUT = "send_to_pvoutput"
CONF_UPLOAD_INTERVAL = "upload_interval"

# Defaults
DEFAULT_UPLOAD_INTERVAL = 5

# Inverter Types - will be loaded from inverter_profiles.json
INVERTER_TYPES = [] 