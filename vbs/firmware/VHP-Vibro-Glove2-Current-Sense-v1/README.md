# VHP-Vibro-Glove2-Current-Sense-v1

This is a specialized firmware branch for the **VHP (Vibro-Tactile Haptics Platform)** that integrates **real-time current sensing** with the standard stimulation protocol.

## 🌟 Key Features

1.  **Based on Stable Core**: Built upon the `SERCOM_2_0_2_BETA` foundation, ensuring reliable volume control and parameter handling.
2.  **Synchronized Current Sensing**: 
    *   Implements intelligent ADC sampling synchronized with the PWM cycle.
    *   **Noise Rejection**: Samples are taken 300µs after the PWM rising edge to avoid switching transients.
    *   **Mux Protection**: Multiplexer channel switching occurs exclusively during the PWM OFF period to prevent arcing and settle-time artifacts.
3.  **Data Logging**: Uses a high-speed ring buffer (`DLog`) to store up to 50,000 current samples (1 second at 50kHz equivalent).

## 🔌 Hardware Configuration

This firmware assumes the following pin mapping for the nRF52840 (MDBT50Q):

*   **Current Sense Input**: Pin **D10 / A6** (P0.03/AIN1).
*   **Mux Enable**: Pin **D2** (P0.02).
*   **I2C Bus (Mux Control)**:
    *   SCL: Pin 25
    *   SDA: Pin 24

## 📜 Serial Commands

In addition to the standard VHP commands (`1`, `0`, `V{n}`, `F{n}`, etc.), this firmware adds:

*   `C`: **Dump Current Log**. detailed CSV output of the current buffer.
    ```csv
    SampleIndex,Current(A)
    0,0.01234
    1,0.01245
    ...
    ```
    *Note: The buffer resets automatically after dumping.*

### 🔍 Understanding the Dump File

| Feature | Details |
| :--- | :--- |
| **Columns** | `SampleIndex` (pulse count), `Current(A)` (measured load in Amps) |
| **Timewise Resolution** | **1 sample per stimulation pulse**. The sampling rate matches your `stimfreq` (e.g., at 32Hz, you get 32 samples/sec). |
| **Channel Mapping** | Logs the **currently active channel**. In a sweep protocol, the log is a continuous stream matching the stimulation sequence. |
| **Measurement Sync** | Sampled **300µs after the pulse start** to capture stable steady-state current after inductive transients. |
| **Filtering** | Uses a **90/10 moving average** to filter out Class D switching noise. |
| **Max Capacity** | **50,000 samples** (~26 minutes at 32Hz). |

This data is intended for verifying **skin-contact quality** and **actuator health**. A lower-than-expected current during an "ON" phase typically indicates the actuator is not under physical load (lack of contact).

## 🧠 Measurement Logic

The `OnPwmSequenceEnd()` interrupt handler drives the measurement loop:

1.  **Check PWM State**: Uses `nrf_pwm_event_check` to determine if we are in the ON or OFF phase.
2.  **Stable Sampling**: If ON and stable (>300µs), reads `analogRead(A6)`.
3.  **Filtering**: Applies a simple 90/10 moving average filter: `y[n] = 0.9*y[n-1] + 0.1*x[n]`.
4.  **Channel Switching**: If the stimulation pattern changes the active channel, the mux switch command is deferred until the next PWM OFF period.

## 🛠️ Building & Flashing

1.  Open `VHP-Vibro-Glove2-Current-Sense-v1.ino` in Arduino IDE.
2.  Ensure you have the `Adafruit nRF52` board support package installed.
3.  Select Board: **Adafruit Feather nRF52840 Sense** (or generic nRF52840).
4.  Compile and Upload.
