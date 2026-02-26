# VHP-Vibro-Glove2-Current-Sense-v1

This is a specialized firmware branch for the **VHP (Vibro-Tactile Haptics Platform)** that integrates **real-time current sensing** with the standard stimulation protocol.

## 🌟 Key Features

1.  **Based on Stable Core**: Built upon the `SERCOM_2_0_2_BETA` foundation, ensuring reliable volume control and parameter handling.
2.  **Synchronized Current Sensing**: 
    *   Implements intelligent ADC sampling synchronized with the PWM cycle.
    *   **High-Speed Sampling**: Samples are taken at the full PWM sequence rate (~5.86 kHz) to capture the AC current waveform.
    *   **Mux Protection**: Multiplexer channel switching occurs exclusively during the PWM OFF period to prevent arcing and settle-time artifacts.
3.  **Data Logging**: Uses a high-speed ring buffer (`DLog`) to store up to **100,000 current samples** (~17 seconds at 5.86kHz).

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
| **Columns** | `SampleIndex`, `Current(A)` |
| **Sample Rate** | **~5,859 Hz** (Samples every PWM sequence completion). |
| **Waveform Capture** | Provides ~183 samples per cycle for a 32Hz sine wave, allowing detailed **AC waveform analysis**. |
| **Channel Mapping** | Logs the **currently active channel**. |
| **Measurement Sync** | Sampled at the start of each new PWM data frame update. |
| **Filtering** | **None** (Raw instantaneous current). |
| **Max Capacity** | **100,000 samples** (~17 seconds of high-res data). |

This data allows you to visualize the **back-EMF** and real-time current dynamics of the voice coil, acting like a digital oscilloscope.

## 🧠 Measurement Logic

The `OnPwmSequenceEnd()` interrupt handler drives the measurement loop:

1.  **Interrupt Trigger**: Fires every ~170µs (when the 8-sample PWM buffer is exhausted).
2.  **Instant Sampling**: Reads `analogRead(A6)` immediately.
3.  **Logging**: Converts to Amps and stores in RAM ring buffer.
4.  **Channel Switching**: Updates multiplexer if the active channel has changed.

## 🛠️ Building & Flashing

1.  Open `VHP-Vibro-Glove2-Current-Sense-v1.ino` in Arduino IDE.
2.  Ensure you have the `Adafruit nRF52` board support package installed.
3.  Select Board: **Adafruit Feather nRF52840 Sense** (or generic nRF52840).
4.  Compile and Upload.
