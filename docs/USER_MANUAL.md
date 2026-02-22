# 🧠 EEGsuite User Manual

Welcome to the **EEGsuite** user manual. This repository is a professional-grade EEG research pipeline designed for high-portability measurements, specifically tailored for Parkinson's Disease studies.

---

## 🏗 System Architecture

The suite consists of three primary layers:
1.  **Hardware & Streaming (`server`)**: Interfaces with EEG hardware (e.g., FreeEEG32) via BrainFlow and broadcasts data to the local network using **Lab Streaming Layer (LSL)**.
2.  **Protocol & Recording (`sweep`)**: Connects to the LSL stream and an external stimulator (VHP device) to run automated experimental protocols.
3.  **Visualization & Analysis (`analyze`)**: Processes recorded CSV/EDF files to generate research-ready plots and metrics.

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
Generates HTML/PDF visualizations of your recorded data.
*   **Usage**: `python -m src.main analyze -f .\data\session_01.csv -s 7.5 -d 2.0`
*   **Options**:
    *   `-f, --file`: Path to the CSV file.
    *   `-s, --start`: Start time in seconds (default: 7.5).
    *   `-d, --duration`: Window size in seconds (default: 2.0).

---

## 📁 Project Structure

*   `/config`: YAML files for hardware and experimental protocols.
*   `/data`: All recordings (CSV/EDF) are stored here.
*   `/logs`: Detailed session logs for debugging.
*   `/src`: The core source code.
    *   `streaming/`: BrainFlow/LSL implementation.
    *   `recording/`: Sweep protocol implementation.
    *   `analysis/`: Data processing tools.

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
