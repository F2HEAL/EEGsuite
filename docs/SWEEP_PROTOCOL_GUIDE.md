# 🕒 Sweep Protocol User Manual

The Sweep Protocol is a structured EEG recording procedure designed to capture neural responses to vibrotactile stimulation while explicitly accounting for electromagnetic (EM) artifacts.

---

## 🛠 Prerequisites

Before starting a sweep, ensure:
1.  **LSL Server is Running**: The EEG data stream must be active (e.g., `python -m src.main LSLserver -c config/hardware/freeeeg.yaml`).
2.  **VHP Device Connected**: The Vibrotactile Haptic Protocol (VHP) board should be connected via USB and powered ON.
3.  **Config Files Ready**:
    - **Hardware Config**: Defines the serial port and board ID (e.g., `config/hardware/freeeeg.yaml`).
    - **Protocol Config**: Defines frequencies, volumes, and timing (e.g., `config/protocols/sweep_default.yaml`).

---

## 🚀 Execution

Run the sweep command from the project root:
```bash
python -m src.main sweep -d config/hardware/freeeeg.yaml -p config/protocols/sweep_default.yaml
```

---

## 📊 Phase 1: The Three Baselines

The protocol begins with three critical baseline measurements to calibrate the environment and the stimulator's artifact profile.

### 1️⃣ Baseline 1: Environmental Noise (VHP OFF/ON)
- **Manual Def**: `Baseline_1` (Pre-start EEG measurement)
- **Procedure**: EEG recording starts *before* the VHP board is powered ON or while it is disconnected.
- **Purpose**: Captures the ambient electrical noise floor of the room and the acquisition system.
- **Marker**: `3`
- **Duration**: Defined in protocol YAML (`Baselines: Baseline_1`), defaulting to 10 seconds.

### 2️⃣ Baseline 2: EM Artifact Template (NO CONTACT)
- **Manual Def**: `Baseline_2` (In-Field-Not-Feeling-Nipple / IFNFN)
- **Procedure**: VHP board is **ON** and stimulation is **ACTIVE**, but the subject's finger is held **5 cm away** from the tactor.
- **Purpose**: Captures the pure electromagnetic (EM) artifact radiated by the stimulator. This is the "artifact template" used for subtraction in TFR analysis.
- **Markers**: 
    - `31`: Stimulation ACTIVE (No contact).
    - `33`: Immediately after stimulation stops.
- **Duration**: Defined in protocol YAML (`Baselines: Baseline_2`).

### 3️⃣ Baseline 3: Pre-Sweep Rest (CONTACT)
- **Manual Def**: `Baseline_3` (Initial Rest)
- **Procedure**: Subject's finger is placed **ON** the tactor, but stimulation is **OFF**.
- **Purpose**: Captures the resting-state EEG while the subject is in physical contact with the hardware, just before a sweep sequence begins.
- **Marker**: `333`
- **Duration**: Defined in protocol YAML (`Baselines: Baseline_3`).

---

## 🔄 Phase 2: The Sweep Sequence

After baselines are complete, the system iterates through the combinations of **Channel**, **Frequency**, and **Volume** defined in your protocol. For each combination, a new CSV file is created.

### Trial Structure
Each sweep file contains multiple cycles (trials) of:
1.  **Rest (Duration_off)**: Marker `0`.
2.  **Stimulation (Duration_on)**: Marker `1`.
3.  **Post-Stim Rest (Duration_off)**: Marker `11`.

---

## 🏷 Marker Reference Table

| Marker | Description | Phase |
| :--- | :--- | :--- |
| **3** | Baseline 1: VHP OFF/ON transition | Calibration |
| **31** | Baseline 2: Stim ON (No physical contact) | Calibration |
| **33** | Baseline 2: Stim OFF (No physical contact) | Calibration |
| **333** | Baseline 3: Pre-Sweep Rest (Physical contact) | Recording |
| **0** | Trial Rest (Inter-stimulus interval) | Recording |
| **1** | Trial Stimulation ON | Recording |
| **11** | Trial Stimulation OFF (Recovery) | Recording |

---

## 📂 Outputs

All data is saved to `data/raw/` with the following naming convention:
- **Baselines**: `[YYMMDD-HHMM]_[BOARD]_baseline_[TYPE].csv`
- **Sweeps**: `[YYMMDD-HHMM]_[BOARD]_c[CHAN]_f[FREQ]_v[VOL].csv`
- **Metadata**: `[YYMMDD-HHMM]_metadata.txt` (Contains the exact hardware and protocol parameters used).
