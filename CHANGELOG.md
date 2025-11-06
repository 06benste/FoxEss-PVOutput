# Changelog

All notable changes to this project will be documented in this file.


## [0.1.2-alpha] - 2025-11-06

### Added
- Debug logging to `pvoutput_uploader.log` file in the custom_components folder. All Modbus operations and parameter detection are now logged with detailed debug information for troubleshooting.
- Automatic parameter style detection for different pymodbus versions. The integration now automatically detects and uses the correct parameter style (`device_id`, `unit`, `slave`, or positional) based on the installed pymodbus version.

### Fixed
- Fixed pymodbus compatibility issues with newer versions that use `device_id` parameter instead of `slave` or `unit`. The integration now works correctly with all pymodbus versions including those bundled with Home Assistant.
- Improved Modbus client error handling and connection state management. Better detection and recovery from connection failures.
- Enhanced Modbus client with optimizations including TCP_NODELAY socket option and connection delay handling for improved reliability.

### Improved
- Modbus client architecture refactored with improved async wrapper, locking mechanisms, and connection state tracking

## [0.1.1-alpha] - 2024-07-05
- Integration entry now uses the PVOutput system name (e.g., 'My Solar Site - PV Output') instead of the IP address. This is fetched using the getsystem.jsp endpoint. You must remove and re-add the integration for the new name to appear.

### Added
- CHANGELOG.md file to track changes.
- Documented a known issue in the README regarding the limited resolution of daily solar data from the inverter, which can cause irregular average values in PVOutput. This is a limitation that would require FoxESS to change the data resolution.
- Real-time validation of Modbus IP, PVOutput API key, and system ID during configuration. The integration now checks connectivity to the inverter and verifies PVOutput credentials before saving the configuration.

### Fixed
- Upload interval is now aligned to the wall clock (e.g., every 5 minutes at :00, :05, :10, etc.), eliminating drift in PVOutput uploads.

--- 
