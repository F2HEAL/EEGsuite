# 🧠 EEGsuite User Manual

Welcome to the **EEGsuite** user manual. This repository is a professional-grade EEG research pipeline designed for high-portability measurements, specifically tailored for Parkinson's Disease studies.

---

## 🏗 System Architecture

The suite consists of three primary layers:
1.  **Hardware & Streaming (`server`)**: Interfaces with EEG hardware (e.g., FreeEEG32) via BrainFlow and broadcasts data to the local network using **Lab Streaming Layer (LSL)**.
2.  **Protocol & Recording (`sweep`)**: Connects to the LSL stream and an external stimulator (VHP device) to run automated experimental protocols.
3.  **Visualization & Analysis (`analyze`)**: Processes recorded CSV/EDF files to generate research-ready plots and metrics.

### 🔌 Hardware Connection Schematic

![System Architecture](assets/system_schematic.png)
*Note: Ensure USB Isolators are used as shown to maintain signal integrity.*

For specific electrode placement used in the KULLAB measurements, see the [KULLAB 32 Montage Documentation](MONTAGE_KULLAB.md).
For the 8-channel motor cortex montage, see the [FREG8 Montage Documentation](MONTAGE_FREG8.md).

The hardware setup is designed for maximum signal purity and participant safety:

*   **Acquisition Node (Left)**: The FreeEEG32 is battery-powered (3x1.5V AA) and connected via a USB Isolator. The acquisition laptop should ideally run on DC power (battery) to eliminate 50/60Hz mains interference.
*   **Control Node (Center)**: The Master laptop manages the protocol and stimulation. It communicates with the acquisition node via a local Ethernet switch for low-latency LSL streaming.
*   **Vibrotactile Stimulator (Right)**: A voice-coil based actuator delivering precise tactile stimuli. It is electrically isolated from the EEG acquisition branch to prevent electromagnetic leakage.

---

## 🚀 Quick Start

### 1. Installation
Ensure you have Python 3.10+ installed. Clone the repository and install dependencies:
```powershell
pip install -r requirements.txt
```

### 2. Configure Your Hardware
Edit `config/hardware/freeeeg.yaml` to match your COM ports:
```yaml
Board:
  Id: FREEEEG32_BOARD
  Serial: "COM3"
VHP:
  Serial: "COM5"
```

---

## 🛠 Command Reference

The suite uses a unified CLI: `python -m src.main <command> [options]`

### `server` (The LSL Bridge)
Starts the BrainFlow driver and creates an LSL stream.
*   **Usage**: `python -m src.main server -c .\config\hardware\freeeeg.yaml`
*   **Action**: Look for the log `* LSL stream 'BrainFlowEEG' is now active`.

### `sweep` (The Experiment Engine)
Runs the automated protocol, controlling both EEG recording and the VHP stimulator.
*   **Usage**: `python -m src.main sweep -d .\config\hardware\freeeeg.yaml -p .\config\protocols\sweep_default.yaml`
*   **Protocol**: It will execute baselines and measurements defined in your protocol YAML.

### `analyze` (The Data Visualizer)
Generates native HTML visualizations of your recorded data using MNE-python.
*   **Usage**: `python -m src.main analyze -f .\data\session_01.csv -s 0.0 -d 60.0`
*   **Action**: Look for the report in the `\reports` folder.
*   **Customization**: Edit `config\analysis\default_offline.yaml` to change channel names, montage, or filter frequencies.
*   **Montage Switching**: To change electrode layouts (e.g., from 32-channel to 8-channel), change the `montage_profile` in `config\analysis\default_offline.yaml`.
    *   `kullab`: Standard 32-channel layout.
    *   `freg8`: Sparse 8-channel motor layout.
*   **Channel Picking**: You can manually override which channels appear in the report by editing the `pick_channels` list in `config\analysis\default_offline.yaml`.
    *   If `pick_channels` is defined in the main YAML, it takes priority over the montage profile's defaults.
    *   This affects all plots: Timeseries, Spectrograms, PSD, and ERPs.
*   **Options**:
    *   `-f, --file`: Path to the CSV file.
    *   `-s, --start`: Start time in seconds (default: 0.0).
    *   `-d, --duration`: Window size in seconds (default: 60.0).

---

## 📁 Project Structure

*   `/config`: YAML files for hardware and experimental protocols.
*   `/data`: All recordings (CSV/EDF) are stored here.
*   `/logs`: Detailed session logs for debugging.
*   `/reports`: Analysis results and visualizations.
*   `/src`: The core source code.
    *   `streaming/`: BrainFlow/LSL implementation.
    *   `recording/`: Sweep protocol implementation.
    *   `analysis/`: Data processing tools.

---

## 🔬 Performance & Timing Precision

This suite is optimized for high-precision academic research. Based on empirical validation:

*   **Timing Accuracy**: See findings in the [Performance Section](#performance--timing-precision).
*   **EM Integrity**: For detailed measurements on stimulator cross-talk and filter effectiveness, see the [Hardware Validation Report](HARDWARE_VALIDATION_EMI.md).

### 1. Synchronization Accuracy
*   **Mean Latency**: $\approx 6.0\text{ms}$ (Command to physical vibration).
*   **Marker Precision**: Event markers are synchronized with EEG data at a resolution of **1.95ms** (at 512 Hz sampling).
*   **Jitter**: $\pm 5\text{ms}$, primarily driven by Windows OS thread scheduling.

### 2. Implementation Details
*   **Non-Blocking Commands**: Critical `Start` (1) and `Stop` (0) serial commands are sent with zero software delay to ensure immediate hardware response.
*   **Deterministic Markers**: Markers are attached to the actual LSL sample timestamps, ensuring that even if there is a small transmission delay, the "Stimulation ON" label in your CSV matches the exact sample where the signal appears.

---

### 💾 Changing Data Storage Location
By default, the system saves data to the `/data` folder in the project root. If your cloud drive is unreachable or you wish to use a different location:

#### Option 1: CLI Override (Recommended for quick changes)
Use the `--data-root` argument before the command:
```powershell
python -m src.main --data-root "C:\MyLocalData" sweep -d .\config\hardware\freeeeg.yaml -p .\config\protocols\sweep_default.yaml
```

#### Option 2: Environment Variable (Persistent)
Set the `EEG_CLOUD_ROOT` environment variable. The system will create `data/`, `logs/`, and `reports/` inside this path.
*   **Windows (PowerShell)**: `[System.Environment]::SetEnvironmentVariable('EEG_CLOUD_ROOT', 'D:\EEG_Storage', 'User')`
*   **Linux/Mac**: `export EEG_CLOUD_ROOT="/path/to/storage"`

---

## 🧪 Development Rules
This project follows strict academic standards:
*   **Determinism**: `RANDOM_SEED: int = 42` is defined in all relevant files.
*   **Paths**: Always use `pathlib.Path`, never strings.
*   **Logging**: No `print()` statements; use `logging.getLogger(__name__)`.
*   **Docstrings**: Follow the Google Python Style Guide.

---

## ❓ Troubleshooting

**"Could not bind multicast responder"**
*   This is a BrainFlow warning. It is usually harmless and does not prevent data streaming.

**"LSL stream not found"**
*   Ensure the `server` command is running in a separate terminal before starting a `sweep`.

**"Serial port permission denied"**
*   Check that no other software (like Arduino IDE or a previous session) is holding the COM port open.
