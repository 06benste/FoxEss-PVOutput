# PVOutput FoxESS Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

This Home Assistant custom component connects to FoxESS inverters via local Modbus TCP over your network to read operational data and automatically upload it to [PVOutput.org](https://pvoutput.org).

> **Note:** This integration has been tested with the Elfin EW11a Modbus-TCP to serial gateway. Other connection methods may work but are unconfirmed.

It polls your inverter locally, meaning you are not reliant on the FoxESS cloud infrastructure, and you can get near real-time data into Home Assistant.

## Features

*   **Local Polling:** Connects directly to your inverter over your local network using Modbus TCP.
*   **Home Assistant Sensors:** Creates sensors in Home Assistant for all the data points in your inverter's profile, including power, energy, voltage, and temperature.
*   **PVOutput Uploads:** Automatically uploads your system's status to your PVOutput account at a configurable interval.
*   **UI Configuration:** Simple to set up from the Home Assistant user interface; no manual YAML configuration is required.

## Installation

This integration is best installed using the Home Assistant Community Store (HACS).

1.  **Add Custom Repository:**
    *   In HACS, go to the "Integrations" page.
    *   Click the three dots in the top right corner and select "Custom repositories."
    *   In the "Repository" field, paste the URL of this GitHub repository.
    *   Select "Integration" as the category and click "Add."
2.  **Install the Integration:**
    *   The "PVOutput FoxESS" integration will now appear in your HACS integrations list.
    *   Click "Install" and follow the prompts.
3.  **Restart Home Assistant:**
    *   After installation, you must restart Home Assistant for the integration to be loaded.

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
*   H1_G2
*   H3
*   H3_PRO
*   KH

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 