# LSL Tools

## Description
LSL Tools is a suite of Python scripts designed to simplify the management and diagnostic process of Lab Streaming Layer (LSL) environments. Whether you are setting up a new EEG system, troubleshooting network synchronization issues, or verifying stream metadata, these tools provide a clear, detailed, and automated way to ensure your data acquisition pipeline is performing optimally.

A collection of utilities for scanning, debugging, and analyzing Lab Streaming Layer (LSL) streams.

## Tools Overview

### 1. LSL Stream Analyser (`lsl_stream_analyser.py`)
A comprehensive tool to inspect LSL stream metadata, verify data flow, and analyze sample rate stability/drift.

**Key Features:**
- Full metadata extraction (Source ID, Hostname, Session ID, etc.)
- Detailed channel information display (Labels, Units, Types)
- Sample rate drift analysis (PPM, error %, jitter)
- Performance testing with different timeout intervals
- **Automatic Logging**: Every run generates a timestamped `.txt` report.

**Usage:**
```powershell
# Analyze default stream (BrainFlowEEG)
python lsl_stream_analyser.py

# Analyze a specific stream by name
python lsl_stream_analyser.py -s "SynAmpsRT"
```

**Output:**
Reports are saved as: `lsl_stream_analysis_[StreamName]_[Date]_[Time].txt`

---

### 2. LSL Stream Scanner (`lsl_stream_scanner.py`)
A tool for discovering all active LSL streams on the network.

**Key Features:**
- Lists all available streams with basic info.
- Tests connectivity for each discovered stream.
- Continuous monitoring mode to detect new or lost streams.

**Usage:**
```powershell
python lsl_stream_scanner.py
```

---

### 3. LSL Stream Mimicers (`lsl_stream_mimicer.py` & `lsl_stream_mimicer2.py`)
Tools to generate synthetic LSL streams for testing and development without requiring physical hardware.

#### **High-Precision Mimicer (`lsl_stream_mimicer.py`)**
Generates a high-quality, precisely-timed synthetic EEG stream modeled after a **SynAmps RT** system.
- **Channels**: 32-channel EEG (10-20 system labels).
- **Signal**: Synthetic alpha (10Hz) and beta (20Hz) rhythms with Gaussian noise.
- **Timing**: Uses a high-precision `perf_counter` loop to maintain a stable 1000Hz sampling rate.

#### **Marker-Enabled Mimicer (`lsl_stream_mimicer2.py`)**
Generates a mock EEG stream accompanied by a secondary **Marker** stream.
- **EEG Stream**: 32-channel noise signal.
- **Marker Stream**: Sends "Stimulus" events at random intervals (~1 per second).
- **Metadata**: Includes XML channel descriptions and unit information.

**Usage:**
```powershell
# Start the high-precision mimic
python lsl_stream_mimicer.py

# Start the marker-enabled mimic
python lsl_stream_mimicer2.py
```

## Requirements
- Python 3.x
- `pylsl`
- `numpy` (for analysis)

Install dependencies:
```powershell
pip install pylsl numpy
```
