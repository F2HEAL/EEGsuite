# VHP-Vibro-Glove2-Current-Sense-v1 (Oscilloscope Mode)

This firmware is now configured as a **40Hz Oscilloscope** for analyzing VHP driver performance.

## 🌟 Key Features (Oscilloscope Mode)

1.  **Forced 40Hz Stimulation**: Defaults to 40Hz sine wave on **WebUI Channel 6** (PCB CH5) at 80% volume.
2.  **Multi-Channel Logging**: Captures **Estimated Voltage**, **Measured Current**, and **Active Channel ID**.
3.  **Low-Pass Filtering**: Includes a 150Hz digital low-pass filter to remove switching noise.
4.  **High-Speed Buffer**: Stores 5000 samples (~0.85s) covering >30 cycles of 40Hz.

## 🔌 Logging Format & Mapping

The `C` command dumps 4 columns. Note the mapping between software and hardware:
*   **WebUI/Serial CH6** maps to **PCB CH5** (0-indexed).
*   The firmware handles this mapping automatically via the `order_pairs` array.

```csv
SampleIndex,Voltage(V),Current(A),ActiveChannel
0,0.0000,0.001234,5
...
```

## 📊 Analysis

Run `python plot_dump.py` to visualize the waveforms. 
*   **Automatic File Selection**: Running without arguments picks the most recent `.csv`/`.log` file.
*   **Time Windowing**: Use `--start 100 --stop 200` to zoom into a specific millisecond range.
*   **Statistics**: Calculates mean voltage, mean current, and standard deviation automatically.

## 🛠️ Configuration

To change back to standard mode, edit `VHP-Vibro-Glove2-Current-Sense-v1.ino` and remove the "FORCED MODE" block in `setup()`.

## 📜 Serial Commands

*   `1` / `0`: Start / Stop 40Hz Stream.
*   `C`: Dump Voltage/Current/Channel Log (Buffer resets after dump).
*   `W`: One-shot VCA Load Estimation (Peak Amps).
*   `w`: Toggle Continuous VCA Load Estimation (every 100ms).
*   `S`: Print Firmware Version.
*   `X`: Parameter string dump.
*   `V<val>`: Set volume (0-100).
*   `F<val>`: Set stimulation frequency (Hz).
*   `C<val>`: Set active channel (1-8).

