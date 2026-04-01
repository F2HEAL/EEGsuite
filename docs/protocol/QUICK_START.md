# 🧪 Experiment Procedure & Quick Start

This guide provides a step-by-step walkthrough for preparing, running, and analyzing EEG measurements within the **EEGsuite** ecosystem.

---

## 1. Preparation
1.  **Open Workspace**:
    *   **VS Code**: Open the `EEGsuite` project folder.
    *   **File Explorer**: Open your data synchronization folder (e.g., `G:/My Drive/SharedData/` or a local equivalent).

2.  **Hardware Connection**:

    *   **2.1 VHP Stimulator (VBS)**
        *   Connect the **VHP Stimulator** to the 'Control PC' (Master). This PC manages sweep control, EEG, and event recording.
        *   **Optional VBS WebUI**: Monitor the Vibrotactile Haptics Platform (files in `vbs/webui/`).
            *   **v2.3**: [Launch v2.3](https://test.heal2.day/webui23/f2heal_webui.html)
            *   **v2.4**: [Launch v2.4](https://test.heal2.day/webui24/f2heal_webui.html)

    *   **2.2 FreeEEG32**
        *   Connect the **FreeEEG32** board to the 'EEG Acquisition PC' (LSL StreamOutlet Server).
        *   Set up the **EEG Visualization PC** (Real-time Monitor) to receive and display EEG data for signal quality assessment.
        *   *Note: These roles (Control, Acquisition, Visualization) can be performed by the same PC or separate machines on the same local network.*

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
    *   Edit `config/hardware/freeeeg_only.yaml`.
    *   Update `Board: Serial` and `VHP: Serial` to match your noted ports (e.g., `COM3` on Windows or `/dev/ttyUSB0` on Linux).

## 2. Start LSL Stream (Acquisition Node)
Run this on the PC connected to the EEG board.

```bash
# Basic start
python -m src.main LSLserver -c config/hardware/freeeeg_only.yaml

# Start with a montage to broadcast electrode names (e.g., F3, F4) via LSL metadata
python -m src.main LSLserver -c config/hardware/freeeeg_only.yaml -m config/montages/freg9.yaml
```
*   **Verify**: Wait for the message `* LSL stream 'BrainFlowEEG' is now active`.

## 3.a Assess LSL Stream Quality (Diagnostic)
Before starting the experiment, verify the LSL stream metadata and timing stability.

```bash
# Run the analyzer from the project root
    python src/utils/lsl-tools-1/lsl_stream_analyser.py
```
*   **Check**: Ensure "Timing quality" is `Excellent` or `Good`.
                Stability assessment: Excellent (laboratory grade)
*   **Metadata**: Verify that electrode labels (if using `-m` in step 2) are correctly displayed in the "CHANNEL NAMES" section.

🎉 Stream connection successful!
Channel names: ['T7', 'C3', 'NC', 'NC', 'T8', 'FC4', 'NC', 'NC', 'FC3', 'C4', 'NC', 'NC', 'CP3', 'CP4', 'NC', 'NC', 'Cz', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'NC', 'Channel 31']


## 3.b Start Real-time Monitor (Visualization Node)
Run this on the 'EEG Visualization PC' to monitor EEG signal quality in real-time. The viewer provides live metrics (PTP, RMS, Line Noise Ratio, Muscle Ratio) and supports virtual channels.

### Recommended (YAML-based)
Uses YAML montage files for flexible channel mapping and virtual channel calculations (e.g., Laplacian referencing).

```bash
# Connect to default stream 'BrainFlowEEG' using a montage
python src/analysis/realtime/EEGlslviewer/src/eeg_viewer_main_yaml.py --config config/montages/freg9.yaml

# Connect to a custom LSL stream name or ID
python src/analysis/realtime/EEGlslviewer/src/eeg_viewer_main_yaml.py --config config/montages/freg9.yaml --lsl-stream "YourStreamName"
```

### Legacy (Fixed Config) [Obsolete]
Uses `src/modules/config_channels.py` for fixed channel mapping.
```bash
python src/analysis/realtime/EEGlslviewer/src/eeg_viewer_main.py
```


## 4. Run Experiment (Control Node)
Run this on the PC connected to the VHP Stimulator.

```bash
python -m src.main sweep -d config/hardware/vbs_only.yaml -p config/protocols/sweep_default.yaml
```

```bash
python -m src.main sweep -d config/hardware/freeeeg.yaml -p config/protocols/sweep_default.yaml
```
*   **Procedure**: Follow the on-screen prompts (e.g., "Press SPACEBAR when ready").
*   **Output**: Data is automatically saved to `data/raw/` (or your configured cloud path).

## 5. Analyze Data (Post-Processing)
Generate HTML reports and plots from the recorded CSV files.

### 5.1 General Analysis (Standard Report)
Used for single-file analysis to inspect signal quality, PSD, and spectrograms.

```bash
# Example: Analyze a specific file from start (0s) to 60s
python -m src.main analyze -f "data/raw/YOUR_FILE_NAME.csv" -s 0 -d 60
```
*   **Result**: Check the `reports/` folder for the generated `.html` analysis file.
*   **Customization**: Edit `config/analysis/default_offline.yaml` to change channel names, montage, or filter frequencies.
*   **Montage Switching**: To change electrode layouts (e.g., from 32-channel to 8-channel), change the `montage_profile` in `config/analysis/default_offline.yaml`.
    *   `kullab`: Standard 32-channel layout.
    *   `freg8`: Sparse 8-channel motor layout.
    *   `freg9`: High-SNR 9-channel motor layout.
*   **Channel Picking**: You can manually override which channels appear in the report by editing the `pick_channels` list in `config/analysis/default_offline.yaml`.
    *   If `pick_channels` is defined in the main YAML, it takes priority over the montage profile's defaults.
    *   This affects all plots: Timeseries, Spectrograms, PSD, and ERPs.

### 5.2 TFR Contrast Analysis (EM Artifact Removal)
Used to isolate neural responses from electromagnetic (EM) interference (e.g., from tactile stimulators) by subtracting a noise-only condition from the task condition.

*   **FOT (Finger-On-Tactor)**: Task condition (Neural + EM + Noise).
*   **IFNFN (In-Field-No-Feeling-Nipple)**: Noise-only condition (EM + Noise).

```bash
# Run the contrast analysis on two files
python -m src.main contrast --fot data/raw/SUBJECT_FOT.csv --ifnfn data/raw/SUBJECT_IFNFN.csv
```
*   **Result**: Generates a high-precision HTML report in `reports/` containing TFR heatmaps for FOT, IFNFN, and the final **Contrast** ($FOT - IFNFN$).
*   **Markers**: Requires files recorded with condition-aware markers (1xx for FOT, 2xx for IFNFN).
*   **Reference**: See `docs/ANALYSIS_TFR_CONTRAST.md` for more details on the 4-step pipeline.
