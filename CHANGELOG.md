# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.11-alpha] - 2024-07-05
- Integration entry now uses the PVOutput system name (e.g., 'My Solar Site - PV Output') instead of the IP address. This is fetched using the getsystem.jsp endpoint. You must remove and re-add the integration for the new name to appear.

### Added
- CHANGELOG.md file to track changes.
- Documented a known issue in the README regarding the limited resolution of daily solar data from the inverter, which can cause irregular average values in PVOutput. This is a limitation that would require FoxESS to change the data resolution.
- Real-time validation of Modbus IP, PVOutput API key, and system ID during configuration. The integration now checks connectivity to the inverter and verifies PVOutput credentials before saving the configuration.

### Fixed
- Upload interval is now aligned to the wall clock (e.g., every 5 minutes at :00, :05, :10, etc.), eliminating drift in PVOutput uploads.

--- 
