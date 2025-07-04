# PVOutput FoxESS Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

This Home Assistant custom component connects to FoxESS inverter via Modbus TCP over your network to read inverter data and automatically upload it to [PVOutput.org](https://pvoutput.org).

> **Note:** This integration has been tested with the Elfin EW11a Modbus-TCP to serial gateway. Other connection methods may work but are unconfirmed.


## Features

*   **Local Polling:** Connects to your inverter over your local network using Modbus TCP.
*   **Home Assistant Sensors:** Creates sensors in Home Assistant for all the data points in your inverter's profile relevant to PVOutput, including power, energy, voltage, and temperature.
*   **PVOutput Uploads:** Automatically uploads your system's status to your PVOutput account at a configurable interval.
*   **UI Configuration:** Simple to set up from the Home Assistant user interface; no manual YAML configuration is required.

## Installation

This integration is best installed using the Home Assistant Community Store (HACS).

1.  **Add Custom Repository:**
    *   In HACS, go to the "Integrations" page.
    *   Click the three dots in the top right corner and select "Custom repositories."
    *   In the "Repository" field, paste the URL of this GitHub repository.
    *   Select "Integration" as the category and click "Add."
2.  **Download the Integration:**
    *   The "PVOutput FoxESS" integration will now appear in your HACS integrations list.
    *   Click "Download" and follow the prompts.
3.  **Restart Home Assistant:**
    *   After downloading, you must restart Home Assistant for the integration to be loaded.

## Configuration

Once installed, you can configure the integration through the Home Assistant UI.

1.  Navigate to **Settings > Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button in the bottom right.
3.  Search for "PVOutput FoxESS" and select it.
4.  Follow the on-screen instructions:
    *   **Step 1:** Enter the Modbus IP address of your inverter and select your inverter model from the dropdown list.
    *   **Step 2:** Enter your PVOutput API Key and System ID, and set your desired upload interval.
    *   You can find your API Key and System ID on your [PVOutput account page](https://pvoutput.org/account.jsp).
5.  Click "Submit," and the integration will be set up.

## Supported Inverters

This integration uses the profiles defined in the `inverter_profiles.json` file. 

**Currently, only the H1-G2 model on latest firmware has been fully tested and is confirmed to be working.**

The following inverter models are theoretically supported based on their profiles, but are awaiting testers to confirm functionality. If you have one of these models and can test the integration, please open an issue to share your results.

*   AC1
*   AC1_G2
*   AC3
*   AIO-AC1
*   AIO-H1
*   AIO-H3
*   H1
*   H3
*   H3_PRO
*   KH

## PVOutput Data Mapping

The following table shows how data from your FoxESS inverter is mapped to PVOutput fields:

| PVOutput Field | PVOutput Description | What does FoxEss call it? |
|----------------|-------------|---------------|
| Date | Date of data upload to PVOutput | N/A - PVOutput Generated |
| Time | Time of data upload to PVOutput | N/A - PVOutput Generated |
| Energy | Total energy generated today (kWh) | PV Production (app stats screen) |
| Efficiency | Calculated by dividing the total energy output (kWh) by the system size (kW) | N/A - PVOutput Generated |
| Power | Current power generation (kW) | PV (app flows screen) |
| Average |  The average power is used to smooth out fluctuations in the instantaneous power readings | N/A - PVOutput Generated |
| Normalised |  Normalised energy per kW panels (kWh/kW) | N/A - PVOutput Generated |
| Temperature | Inverter temperature (°C) | Inverter Temperature |
| Voltage | Grid voltage (V) | Grid Voltage - `grid_voltage_R` or `rvolt` or `rvolt_R` or `rvolt_A` (depending on inverter model) |
| Energy Used | Total energy consumed today (kWh) | From Grid (app stats screen) |
| Power Used | Current power consumption (kW) | Load (app flows screen) |

## Known Issues

### Daily Solar Data Resolution

A known issue is that the FoxESS inverter only provides daily solar data at a limited resolution. This can cause the average values reported in PVOutput to appear irregular or less accurate than expected. Unfortunately, this is a limitation of the inverter itself, and would require FoxESS to change the resolution of the data it provides in order to resolve this issue.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 

## Acknowledgements
Inverter register information was sourced and adapted from https://github.com/nathanmarlor/foxess_modbus, with thanks to the original author for their work.

