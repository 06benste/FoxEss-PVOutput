import asyncio
import inspect
import logging
import os
import socket
import time
from enum import Enum
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, TypeVar
from dataclasses import dataclass

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

_LOGGER = logging.getLogger(__name__)

# Set up file logging for debug messages (shared with sensor.py)
_pvoutput_log_file = os.path.join(os.path.dirname(__file__), 'pvoutput_uploader.log')
_pvoutput_logger = logging.getLogger('pvoutput_uploader')
# Only add handler if not already added (to avoid duplicates)
if not _pvoutput_logger.handlers:
    _pvoutput_logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(_pvoutput_log_file, maxBytes=5*1024*1024, backupCount=1)
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
    handler.setFormatter(formatter)
    _pvoutput_logger.addHandler(handler)

T = TypeVar("T")

# How many failed polls before we mark as disconnected
_NUM_FAILED_POLLS_FOR_DISCONNECTION = 5

# Poll delay for LAN connections (30ms)
_POLL_DELAY = 30 / 1000


class ConnectionState(Enum):
    """Connection state enum."""
    INITIAL = 0
    DISCONNECTED = 1
    CONNECTED = 2


@dataclass
class InvalidRegisterRanges:
    """Tracks invalid register ranges."""
    
    @dataclass
    class Range:
        start: int
        count: int
    
    def __init__(self) -> None:
        self._ranges: list[InvalidRegisterRanges.Range] = []
    
    @property
    def is_empty(self) -> bool:
        return len(self._ranges) == 0
    
    def add(self, register: int) -> None:
        """Add an invalid register."""
        # Check if it falls in any existing range
        for x in self._ranges:
            if register >= x.start and register < (x.start + x.count):
                return  # Already covered
            if register == (x.start + x.count):
                x.count += 1
                return
        self._ranges.append(self.Range(register, 1))
    
    def __contains__(self, item: int) -> bool:
        return any(item >= x.start and item < x.start + x.count for x in self._ranges)


class CustomModbusTcpClient(ModbusTcpClient):
    """Custom ModbusTcpClient with optimizations."""
    
    def __init__(self, host: str, port: int = 502, delay_on_connect: float = 1.0, **kwargs: Any) -> None:
        """Initialize custom Modbus TCP client."""
        super().__init__(host, port=port, **kwargs)
        self._host = host
        self._port = port
        self._delay_on_connect = delay_on_connect
    
    def connect(self) -> bool:
        """Connect with optimizations."""
        was_connected = self.socket is not None
        if not was_connected:
            _LOGGER.debug("Connecting to %s:%s", self._host, self._port)
            _pvoutput_logger.debug(f"Modbus: Connecting to {self._host}:{self._port}")
        
        is_connected = super().connect()
        
        # Disable Nagle's algorithm for faster response times
        if not was_connected and is_connected and self.socket:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
            if self._delay_on_connect > 0:
                time.sleep(self._delay_on_connect)
        
        return is_connected


class ModbusClientFailedError(Exception):
    """Raised when Modbus client fails."""
    
    def __init__(self, message: str, response: Any) -> None:
        super().__init__(f"{message}: {response}")
        self.message = message
        self.response = response


class ImprovedModbusClient:
    """Improved Modbus client with async wrapper, locking, and optimizations."""
    
    def __init__(self, hass: Any, host: str, port: int = 502, slave: int = 247) -> None:
        """Initialize improved Modbus client."""
        self._hass = hass
        self._host = host
        self._port = port
        self._slave = slave
        self._lock = asyncio.Lock()
        self._client: CustomModbusTcpClient | None = None
        self._connection_state = ConnectionState.INITIAL
        self._num_failed_poll_attempts = 0
        self._current_connection_error: str | None = None
        self._detected_invalid_ranges = InvalidRegisterRanges()
        self._use_positional = None  # Will be detected on first use
        self._slave_param_name = None  # Will be 'slave', 'unit', or 'device_id' when detected
        self._use_keyword_count = False  # Whether count must be passed as keyword argument
    
    async def close(self) -> None:
        """Close connection."""
        if self._client and self._client.is_socket_open():
            await self._async_pymodbus_call(self._client.close, auto_connect=False)
            self._client = None
    
    @property
    def is_connected(self) -> bool:
        """Return if connected."""
        return self._connection_state == ConnectionState.INITIAL or self._connection_state == ConnectionState.CONNECTED
    
    @property
    def current_connection_error(self) -> str | None:
        """Return current connection error."""
        return self._current_connection_error
    
    async def read_holding_registers(self, start_address: int, count: int) -> list[int]:
        """Read holding registers."""
        if not self._client:
            self._client = CustomModbusTcpClient(self._host, port=self._port, delay_on_connect=1.0)
            _pvoutput_logger.debug(f"Modbus: Created client for {self._host}:{self._port}")
        
        # Detect parameter style on first use
        if self._use_positional is None:
            _pvoutput_logger.debug("Modbus: Detecting parameter style...")
            await self._detect_parameter_style()
        
        # Read registers - handle positional vs keyword arguments
        if self._use_positional is True:
            # Positional: address, count, slave
            response = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                start_address,
                count,
                self._slave,
            )
        elif self._use_positional is False:
            # Use keyword argument - use the detected parameter name
            if self._slave_param_name is None:
                # Should not happen, but fallback to 'slave'
                self._slave_param_name = 'slave'
            
            kwargs = {self._slave_param_name: self._slave}
            # If device_id is used, count must also be a keyword argument
            if self._use_keyword_count:
                kwargs['count'] = count
                response = await self._async_pymodbus_call(
                    self._client.read_holding_registers,
                    start_address,
                    **kwargs,
                )
            else:
                response = await self._async_pymodbus_call(
                    self._client.read_holding_registers,
                    start_address,
                    count,
                    **kwargs,
                )
        else:
            # No slave/unit parameter needed (maybe set on client or not required)
            response = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                start_address,
                count,
            )
        
        if response.isError():
            error_msg = f"Error reading registers. Start: {start_address}; count: {count}; slave: {self._slave}"
            _pvoutput_logger.error(f"Modbus: {error_msg} - {response}")
            raise ModbusClientFailedError(error_msg, response)
        
        _pvoutput_logger.debug(f"Modbus: Successfully read {count} register(s) starting at {start_address}")
        return list(response.registers)
    
    async def _detect_parameter_style(self) -> None:
        """Detect whether to use positional or keyword arguments."""
        if not self._client:
            self._client = CustomModbusTcpClient(self._host, port=self._port, delay_on_connect=1.0)
        
        test_address = 31006  # Common register for testing
        
        # First, inspect the actual function signature to see what parameters it accepts
        try:
            import inspect
            sig = inspect.signature(self._client.read_holding_registers)
            params = list(sig.parameters.keys())
            _LOGGER.debug(f"read_holding_registers signature parameters: {params}")
            
            # Check if it has 'device_id', 'slave', or 'unit' parameter
            if 'device_id' in params:
                self._use_positional = False
                self._slave_param_name = 'device_id'
                self._use_keyword_count = True  # New flag: count must be keyword too
                _LOGGER.debug("Detected 'device_id' parameter in signature")
                _pvoutput_logger.debug(f"Modbus: Detected 'device_id' parameter in signature. Available parameters: {params}")
                return
            elif 'slave' in params:
                self._use_positional = False
                self._slave_param_name = 'slave'
                self._use_keyword_count = False
                _LOGGER.debug("Detected 'slave' parameter in signature")
                _pvoutput_logger.debug(f"Modbus: Detected 'slave' parameter in signature. Available parameters: {params}")
                return
            elif 'unit' in params:
                self._use_positional = False
                self._slave_param_name = 'unit'
                self._use_keyword_count = False
                _LOGGER.debug("Detected 'unit' parameter in signature")
                _pvoutput_logger.debug(f"Modbus: Detected 'unit' parameter in signature. Available parameters: {params}")
                return
            else:
                # No slave/unit/device_id parameter - might be positional or set on client
                _LOGGER.debug(f"No 'slave', 'unit', or 'device_id' parameter found. Available parameters: {params}")
                _pvoutput_logger.debug(f"Modbus: No 'slave', 'unit', or 'device_id' parameter found. Available parameters: {params}")
        except Exception as e:
            _LOGGER.debug(f"Could not inspect signature: {e}")
        
        # Try keyword 'device_id' first (newest pymodbus versions)
        try:
            test_result = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                test_address,
                count=1,
                device_id=self._slave,
            )
            if not test_result.isError():
                self._use_positional = False
                self._slave_param_name = 'device_id'
                self._use_keyword_count = True
                _LOGGER.debug("Detected pymodbus uses keyword 'device_id' parameter")
                _pvoutput_logger.debug("Modbus: Detected pymodbus uses keyword 'device_id' parameter")
                return
        except (TypeError, AttributeError) as e:
            _LOGGER.debug(f"Keyword 'device_id' failed: {e}")
            _pvoutput_logger.debug(f"Modbus: Keyword 'device_id' failed: {e}")
        
        # Try keyword 'slave' (older pymodbus versions)
        try:
            test_result = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                test_address,
                1,
                slave=self._slave,
            )
            if not test_result.isError():
                self._use_positional = False
                self._slave_param_name = 'slave'
                self._use_keyword_count = False
                _LOGGER.debug("Detected pymodbus uses keyword 'slave' parameter")
                _pvoutput_logger.debug("Modbus: Detected pymodbus uses keyword 'slave' parameter")
                return
        except (TypeError, AttributeError) as e:
            _LOGGER.debug(f"Keyword 'slave' failed: {e}")
            _pvoutput_logger.debug(f"Modbus: Keyword 'slave' failed: {e}")
        
        # Try keyword 'unit' (newer pymodbus versions)
        try:
            test_result = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                test_address,
                1,
                unit=self._slave,
            )
            if not test_result.isError():
                self._use_positional = False
                self._slave_param_name = 'unit'
                self._use_keyword_count = False
                _LOGGER.debug("Detected pymodbus uses keyword 'unit' parameter")
                _pvoutput_logger.debug("Modbus: Detected pymodbus uses keyword 'unit' parameter")
                return
        except (TypeError, AttributeError) as e:
            _LOGGER.debug(f"Keyword 'unit' failed: {e}")
            _pvoutput_logger.debug(f"Modbus: Keyword 'unit' failed: {e}")
        
        # Try positional last (older pymodbus versions
        try:
            test_result = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                test_address,
                1,
                self._slave,
            )
            if not test_result.isError():
                self._use_positional = True
                self._slave_param_name = None  # Not used for positional
                self._use_keyword_count = False
                _LOGGER.debug("Detected pymodbus accepts positional 'slave' parameter")
                _pvoutput_logger.debug("Modbus: Detected pymodbus accepts positional 'slave' parameter")
                return
        except (TypeError, AttributeError) as e:
            _LOGGER.debug(f"Positional parameter failed: {e}")
            _pvoutput_logger.debug(f"Modbus: Positional parameter failed: {e}")
        
        # Try without any slave/unit parameter (maybe it's set on the client)
        try:
            test_result = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                test_address,
                1,
            )
            if not test_result.isError():
                self._use_positional = None  # Special value meaning no parameter needed
                self._slave_param_name = None
                self._use_keyword_count = False
                _LOGGER.debug("Detected pymodbus does not require slave/unit parameter")
                _pvoutput_logger.debug("Modbus: Detected pymodbus does not require slave/unit parameter")
                return
        except (TypeError, AttributeError) as e:
            _LOGGER.debug(f"No parameter failed: {e}")
            _pvoutput_logger.debug(f"Modbus: No parameter failed: {e}")
        
        # If all failed, log error with signature info
        error_msg = (
            "Failed to determine pymodbus parameter style. "
            "Tried: keyword 'device_id', keyword 'slave', keyword 'unit', positional, and no parameter. "
            "Please check pymodbus version compatibility."
        )
        _LOGGER.error(error_msg)
        _pvoutput_logger.error(f"Modbus: {error_msg}")
        # Default to trying device_id with keyword count (most likely for newer versions)
        self._use_positional = False
        self._slave_param_name = 'device_id'
        self._use_keyword_count = True
    
    async def _async_pymodbus_call(
        self, call: Callable[..., T], *args: Any, auto_connect: bool = True, **kwargs: Any
    ) -> T:
        """Convert async to sync pymodbus call with locking."""
        
        def _call() -> T:
            if not self._client:
                raise ConnectionException("Client not initialized")
            
            if auto_connect and not self._client.connected:
                if not self._client.connect():
                    raise ConnectionException(f"Failed to connect to {self._host}:{self._port}")
            
            # Call with provided args and kwargs
            return call(*args, **kwargs)
        
        async with self._lock:
            result = await self._hass.async_add_executor_job(_call)
            # Poll delay for stability
            if _POLL_DELAY > 0:
                await asyncio.sleep(_POLL_DELAY)
            return result
    
    def _update_connection_state(self, success: bool, error: Exception | None = None) -> None:
        """Update connection state based on operation result."""
        if success:
            self._num_failed_poll_attempts = 0
            if self._connection_state == ConnectionState.INITIAL:
                self._connection_state = ConnectionState.CONNECTED
            elif self._connection_state == ConnectionState.DISCONNECTED:
                _LOGGER.info("Connection restored to %s:%s", self._host, self._port)
                _pvoutput_logger.info(f"Modbus: Connection restored to {self._host}:{self._port}")
                self._connection_state = ConnectionState.CONNECTED
                self._current_connection_error = None
        else:
            self._num_failed_poll_attempts += 1
            if self._num_failed_poll_attempts >= _NUM_FAILED_POLLS_FOR_DISCONNECTION:
                if self._connection_state != ConnectionState.DISCONNECTED:
                    error_msg = str(error) if error else "Unknown error"
                    _LOGGER.warning(
                        "%s failed poll attempts: now disconnected. Last error: %s",
                        self._num_failed_poll_attempts,
                        error_msg,
                    )
                    _pvoutput_logger.warning(
                        f"Modbus: {self._num_failed_poll_attempts} failed poll attempts: now disconnected. Last error: {error_msg}"
                    )
                    self._connection_state = ConnectionState.DISCONNECTED
                    self._current_connection_error = error_msg
    

