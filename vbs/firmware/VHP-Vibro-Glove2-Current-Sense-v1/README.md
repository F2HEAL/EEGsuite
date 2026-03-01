# VHP-Vibro-Glove2-Current-Sense-v1 (Oscilloscope Mode)

This firmware is now configured as a **40Hz Oscilloscope** for analyzing VHP driver performance.

## 🌟 Key Features (Oscilloscope Mode)

1.  **Forced 40Hz Stimulation**: Defaults to 40Hz sine wave on Channel 1 at 80% volume.
2.  **Dual-Channel Logging**: Captures both **Estimated Voltage** (from PWM) and **Measured Current**.
3.  **Low-Pass Filtering**: Includes a 150Hz digital low-pass filter to remove switching noise.
4.  **High-Speed Buffer**: Stores 5000 samples (~0.85s) covering >30 cycles of 40Hz.

## 🔌 Logging Format & Mapping

The `C` command dumps 3 columns. Note the mapping between software and hardware:
*   **WebUI/Serial CH1** maps to **PCB CH8** (0-indexed) or **CH9** (1-indexed).
*   The firmware automatically handles this mapping using the `order_pairs` array.

```csv
SampleIndex,Voltage(V),Current(A)
0,0.0000,0.001234
...
```

## 📊 Analysis

Run `python plot_dump.py` to see the voltage and current waveforms aligned in time. This allows you to verify phase relationships and driver behavior.

## 🛠️ Configuration

To change back to standard mode, edit `VHP-Vibro-Glove2-Current-Sense-v1.ino` and remove the "FORCED MODE" block in `setup()`.

## 📜 Serial Commands

*   `1`: Start 40Hz Stream
*   `0`: Stop Stream (and stop continuous load output)
*   `C`: Dump Voltage/Current Log (Buffer reset after dump)
*   `W`: One-shot VCA Load Estimation (Peak Amps)
*   `w`: Toggle Continuous VCA Load Estimation (every 100ms)
*   `S`: Status / Version Info
*   `X`: Parameter string dump (includes `W` for load)

