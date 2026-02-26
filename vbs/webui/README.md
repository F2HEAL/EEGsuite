# F2Heal WebUI

## Overview
The **F2Heal WebUI** is a web-based interface designed to control and monitor the **VHP (Vibrotactile Haptics Platform)** device. It enables researchers and clinicians to interact with the device via Bluetooth Low Energy (BLE) to deliver precise vibrotactile stimulation for somatosensory research (e.g., SSSEP).

**Live Version (v2.3)**: [https://test.heal2.day/webui23/f2heal_webui.html](https://test.heal2.day/webui23/f2heal_webui.html)  
**Beta Version (v2.4 - Mobile Optimized)**: [https://test.heal2.day/webui24/f2heal_webui.html](https://test.heal2.day/webui24/f2heal_webui.html)

The interface is built using standard web technologies (HTML, CSS, JavaScript) and utilizes the **Web Bluetooth API** to communicate with devices advertising the Nordic UART Service (NUS).

## Core Functionalities

### 1. BLE Connectivity
- **Device Discovery**: Scans for devices with the name prefix `Audio-to-Tactile`.
- **Communication**: Uses the Nordic UART Service (NUS) for bi-directional data exchange.
- **Connection Management**: Real-time connection/disconnection toggling.

### 2. Device Control & Configuration
- **Stream Control**: Start and stop the stimulation stream.
- **Amplitude Control**: Fine-tune the stimulation intensity (0-100).
- **Advanced Parameters**:
  - **Stimulation Frequency**: Range 20Hz - 400Hz.
  - **Stimulation Duration**: Range 1ms - 65535ms.
  - **Channel Modes**: Toggle between 8-channel single mode and 4-channel mirrored mode.
  - **Cycle Settings**: Configure cycle periods, pause cycles, and jitter.

### 3. Monitoring & Feedback
- **Status Panel**: Real-time display of firmware version, battery voltage, and running status.
- **Logging**: Integrated log viewer for monitoring BLE messages and system events.

### 4. Presets
- Load and apply pre-defined stimulation protocols from a `presets.json` configuration file.
- Support for URL parameters to auto-load specific presets (e.g., `?preset=Name`).

## Project Structure (v2.3)
The latest version (found in `webui23/`) consists of:
- `f2heal_webui.html`: The main user interface structure.
- `f2heal_webui.js`: Handles UI interactions and preset management.
- `f2heal_library.js`: The core library for BLE communication, message encoding/decoding, and device management.
- `f2heal_webui.css`: Custom styling for the interface.
- `presets.json`: A JSON database of pre-defined stimulation settings.

## Hardware Compatibility
- **Device**: VHP Vibrotactile Haptics Platform.
- **Firmware Requirement**: Requires FW `SERCOM_2_0_2_BETA` or higher for full feature support.

## Usage
To use the WebUI:
1. Open `f2heal_webui.html` in a Web Bluetooth-compatible browser (e.g., Google Chrome, Microsoft Edge).
2. Click **Connect** and select the "Audio-to-Tactile" device from the list.
3. Once connected, use the **Refresh** button to pull the current state from the device.
4. Adjust parameters manually or select a **Preset** to apply settings.
5. Click **Start Stream** to begin stimulation.
