# 🧪 Experiment Procedure & Quick Start

This guide provides a step-by-step walkthrough for preparing, running, and analyzing EEG measurements within the **EEGsuite** ecosystem.

---

## 1. Preparation
1.  **Open Workspace**:
    *   **VS Code**: Open the `EEGsuite` project folder.
    *   **File Explorer**: Open your data synchronization folder (e.g., `G:/My Drive/SharedData/` or a local equivalent).

2.  **Hardware Connection**:
    *   Connect the **FreeEEG32** board to the 'EEG Acquisition PC' (LSL StreamOutlet Server).
    *   Connect the **VHP Stimulator** (VBS) to the 'Control PC' (Master: Sweep control, EEG, and event recording).
    *   Set up the **EEG Visualization PC** (Real-time Monitor) to receive and display EEG data for signal quality assessment.
    *   *Note: These roles can be performed by the same PC or separate machines on the same local network.*

3.  **Verify Serial Ports**:
    *   **Windows**: Open Device Manager (`devmgmt.msc`) and note the COM ports (e.g., `COM3`, `COM5`).
    *   **Linux**: Run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`. Use `sudo dmesg | tail` after plugging in a device to identify it (e.g., `/dev/ttyUSB0`). Example dmesg output below:

```[456806.703538] usb 3-9: new full-speed USB device number 34 using xhci_hcd
[456807.099733] usb 3-9: Device not responding to setup address.
[456807.319957] usb 3-9: New USB device found, idVendor=239a, idProduct=8029, bcdDevice= 1.00
[456807.319963] usb 3-9: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[456807.319965] usb 3-9: Product: Feather nRF52840 Express
[456807.319967] usb 3-9: Manufacturer: Adafruit
[456807.319968] usb 3-9: SerialNumber: 04D80A9201CF428B
[456807.321751] cdc_acm 3-9:1.0: ttyACM0: USB ACM device
[456819.944441] usb 3-3: new full-speed USB device number 35 using xhci_hcd
[456820.070209] usb 3-3: New USB device found, idVendor=0483, idProduct=5740, bcdDevice= 2.00
[456820.070214] usb 3-3: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[456820.070215] usb 3-3: Product: STM32 Virtual ComPort
[456820.070216] usb 3-3: Manufacturer: STMicroelectronics
[456820.070217] usb 3-3: SerialNumber: 3966375A3430
[456820.071711] cdc_acm 3-3:1.0: ttyACM1: USB ACM device
```

4.  **Configuration**:
    *   Edit `config/hardware/freeeeg.yaml`.
    *   Update `Board: Serial` and `VHP: Serial` to match your noted ports (e.g., `COM3` on Windows or `/dev/ttyUSB0` on Linux).

## 2. Start LSL Stream (Acquisition Node)
Run this on the PC connected to the EEG board.

```bash
# Basic start
python -m src.main LSLserver -c config/hardware/freeeeg_only.yaml

# Start with a montage to broadcast electrode names (e.g., F3, F4) via LSL metadata
python -m src.main LSLserver -c config/hardware/freeeeg_only.yaml -m config/montages/freg8.yaml
```
*   **Verify**: Wait for the message `* LSL stream 'BrainFlowEEG' is now active`.

## 3.a Assess LSL Stream Quality (Diagnostic)
Before starting the experiment, verify the LSL stream metadata and timing stability.

```bash
# Run the analyzer from the project root
python src/utils/lsl-tools-1/lsl_stream_analyser.py
```
*   **Check**: Ensure "Timing quality" is `Excellent` or `Good`.
*   **Metadata**: Verify that electrode labels (if using `-m` in step 2) are correctly displayed in the "CHANNEL NAMES" section.

## 3.b Start Real-time Monitor (Visualization Node)
Run this on the 'EEG Visualization PC' from the [EEGlslviewer](https://github.com/F2HEAL/EEGlslviewer) repository to monitor signal quality.

```bash
python eeg_viewer_main.py
```
*   **Default**: Connects to the "BrainFlowEEG" LSL stream. 
*   **Custom**: To specify a different stream name, use: `python eeg_viewer_main.py --lsl-stream "YourStreamName"`


## 4. Run Experiment (Control Node)
Run this on the PC connected to the VHP Stimulator.

```bash
python -m src.main sweep -d config/hardware/freeeeg.yaml -p config/protocols/sweep_default.yaml
```
*   **Procedure**: Follow the on-screen prompts (e.g., "Press SPACEBAR when ready").
*   **Output**: Data is automatically saved to `data/raw/` (or your configured cloud path).

## 5. Analyze Data (Post-Processing)
Generate HTML reports and plots from the recorded CSV files.

```bash
# Example: Analyze a specific file from start (0s) to 60s
python -m src.main analyze -f "data/raw/YOUR_FILE_NAME.csv" -s 0 -d 60
```
*   **Result**: Check the `reports/` folder for the generated `.html` analysis file.
*   **Customization**: Edit `config/analysis/default_offline.yaml` to change channel names, montage, or filter frequencies.
*   **Montage Switching**: To change electrode layouts (e.g., from 32-channel to 8-channel), change the `montage_profile` in `config/analysis/default_offline.yaml`.
    *   `kullab`: Standard 32-channel layout.
    *   `freg8`: Sparse 8-channel motor layout.
*   **Channel Picking**: You can manually override which channels appear in the report by editing the `pick_channels` list in `config/analysis/default_offline.yaml`.
    *   If `pick_channels` is defined in the main YAML, it takes priority over the montage profile's defaults.
    *   This affects all plots: Timeseries, Spectrograms, PSD, and ERPs.
