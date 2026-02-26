# VHP Firmware

This directory contains the firmware source code for the **VHP (Vibrotactile Haptics Platform)** device (also referred to as VBS).

## 📂 Firmware Versions

### 1. [VHP-Vibro-Glove2](VHP-Vibro-Glove2/) (Main)
*   **Version**: `SERCOM_2_0_2_BETA`
*   **Description**: The current stable release for production use.
*   **Key Features**: 
    *   Volume correction for consistent stimulation intensity.
    *   Extended parameter string support for BLE/Serial communication.
    *   Optimized timing for high-precision academic research.

### 2. [VHP-Vibro-Glove2-current-feedback](VHP-Vibro-Glove2-current-feedback/) (Experimental)
*   **Version**: `1.0.0-currenttest`
*   **Description**: Experimental branch for load condition monitoring.
*   **Objective**: Implements **Current Measurement** of VCA (Voice Coil Actuator) consumption.
*   **Implementation**: Uses `Max14661` mux and `DLog1` for high-speed current logging to provide feedback on the physical load/skin-contact status.

### 3. [VHP-Vibro-Glove2-Current-Sense-v1](VHP-Vibro-Glove2-Current-Sense-v1/) (New)
*   **Version**: `SERCOM_2_0_3_CURRENT_SENSE_v1`
*   **Description**: The integrated solution merging stable core features with advanced sensing.
*   **Key Features**:
    *   Synchronized ADC sampling (avoiding PWM noise).
    *   Protected Mux switching (during OFF cycles only).
    *   New `C` serial command for dumping data buffers.

---

## Technical Documentation

For hardware developers working on the experimental current-feedback branch:
*   [VHP Current Sensing Circuit](VHP-Vibro-Glove2-current-feedback/VHP%20Current%20sensing%20Circuit.md): Details on ADC configuration, resolution, and voltage ranges for the nRF52.
*   [ADC & PWM Synchronization Guide](VHP-Vibro-Glove2-current-feedback/The%20synchronization%20between%20ADC%20measurements%20and%20MUX%20PWM.md): Best practices for timing measurements to avoid PWM switching noise and MUX artifacts.

---

## �🛠️ Build Instructions
1.  Install the **Arduino IDE** or **VS Code + PlatformIO**.
2.  Install the **nRF52** board support package (Adafruit nRF52).
3.  Open the `.ino` file in the respective version folder.
4.  Compile and upload to the VHP board via USB or programmer.
