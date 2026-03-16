# 🧠 EEG Measurement Protocol: 42 Hz Tactile Stimulation (FREG8)

**Project:** Academic EEG Research Pipeline for Parkinson's Disease (EEGsuite)
**Objective:** Establish a robust method to isolate the neural response to 42 Hz tactile stimulation while suppressing electromagnetic (EM) noise using a sparse 8-channel motor montage (FREG8).

---

## 1. Rationale & Frequency Selection
### Why 42 Hz?
To minimize spectral leakage from the 50 Hz power line and its harmonics (100, 150, 200 Hz), 42 Hz is selected as the optimal test frequency.
*   **Buffer:** Maintains a strictly $\ge$ 8 Hz margin from all 50 Hz harmonics up to 200 Hz.
*   **Harmonics:** 1st (42Hz), 2nd (84Hz), 3rd (126Hz), 4th (168Hz), 5th (210Hz).
*   **Stability:** Integer values ensure reproducible digital synthesis relative to the sampling rate.

---

## 2. Experimental Conditions (Core Strategy)
The protocol uses a **Contrast Strategy** (FOT - IFNFN) to cancel EM noise, environmental noise, and non-task-related brain activity.

### Condition 1: Finger-On-Tactor (FOT)
*   Finger rests directly on the functional mechanical contact nipple.
*   **Stimulation:** True tactile + EM noise present.

### Condition 2: Finger In Noise Field, Not Feeling Nipple (IFNFN)
*   Nipple is removed or disabled. Finger rests on the tactor case or support in the same EM field.
*   **Stimulation:** EM noise present, NO tactile stimulation.
*   **Consistency:** Finger position must be identical to FOT using a fixed cradle or alignment marker.

---

## 3. Hardware Setup (FREG8 Montage)
This protocol uses the **FreeEEG32** board and the **Tenocom 32ch Cap** mapped to 8 active channels.

### Electrode Placement (10-20 System)
| Location | FreeEEG Channel | Description |
| :--- | :--- | :--- |
| **T7** | CH 01 | Left Temporal |
| **C3** | CH 02 | Left Central (Primary Motor) |
| **T8** | CH 05 | Right Temporal |
| **FC4** | CH 06 | Right Fronto-Central |
| **FC3** | CH 09 | Left Fronto-Central |
| **C4** | CH 10 | Right Central (Primary Motor) |
| **CP3** | CH 13 | Left Centro-Parietal |
| **CP4** | CH 14 | Right Centro-Parietal |

### Reference & Ground (Critical)
*   **REFERENCE (REF):** Linked Ears (Ear clips on both lobes).
*   **GND/BIAS:** Forehead (FPZ) or Midline Frontal (FZ).

### Diagnostic Channels
*   **CH 26:** Shorted with a jumper (Noise floor monitoring).
*   **CH 30:** Open/Floating.

---

## 4. Preparation Step-by-Step

### A. Environment & Hardware
1.  **Shut down** non-essential electronic devices.
2.  **Connect** FreeEEG32 to the Acquisition PC and VBS Stimulator to the Control PC.
3.  **Verify COM Ports** in Windows Device Manager.
4.  **Update Config:** Edit `.\config\hardware\freeeeg.yaml` with correct serial ports.

### B. Patient Preparation
1.  **Measure:** Locate Cz (vertex) and mark the head.
2.  **Cap Placement:** Align cap Cz with vertex mark; secure chin strap.
3.  **Skin Prep:** Use prep paste/alcohol at the 8 active sites + Earlobes + Forehead.
4.  **Gel Application:** Fill until gel touches the electrode sensor.
5.  **Impedance Check:** Ensure all active electrodes are **< 5 kΩ**.

---

## 5. Software Execution

### 1. Start LSL Stream (Acquisition Node)
```powershell
python -m src.main LSLserver -c .\config\hardware\freeeeg.yaml
```

### 2. Start Real-time Monitor (Visualization Node)
Verify signal quality (look for clean baseline, no excessive 50Hz noise).
```powershell
python eeg_viewer_main.py
```

### 3. Start Experiment Control (Control Node)
```powershell
python -m src.main sweep -d .\config\hardware\freeeeg.yaml -p .\config\protocols\sweep_default.yaml
```

---

## 6. Experimental Procedure (Blocked Protocol)

### Phase 1: Control & Baseline (10 mins)
1.  **Device OFF Baseline (1 min):** Sit quietly, eyes open. Record resting state.
2.  **Device ON, No Contact (1 min):** Finger on support, tactor vibrating at 42 Hz in air near finger.
3.  **Analysis Check:** Check for EM or audio contamination. If noise floor increases significantly, troubleshoot grounding.

### Phase 2: Neurostimulation (50-100 cycles per condition)
Each cycle: $\ge$ 1s Pre-stim baseline, 4s Stimulation, Optional post-stim.

1.  **Block 1: FOT (Finger On Tactor)**
    *   Place nipple on tactor.
    *   Instruct subject: "Place finger on the nipple."
    *   Run 50-100 cycles at 42 Hz.
2.  **Block 2: IFNFN (Finger In Noise Field)**
    *   **Remove the nipple** from the tactor.
    *   Instruct subject: "Place finger on the tactor case." (Maintain exact position).
    *   Run 50-100 cycles at 42 Hz.

---

## 7. Post-Processing & Analysis

### 1. Generate Report
```powershell
# Analyze the recorded CSV
python -m src.main analyze -f "data/raw/YOUR_FILE.csv" -s 0 -d 60
```
*   **Config:** Set `montage_profile: freg8` in `config\analysis\default_offline.yaml`.

### 2. Data Processing Pipeline (Time-Frequency)
1.  **TFR Transform:** Apply Morlet wavelets to the entire recording.
2.  **Epoching:** 
    *   Baseline: -1.0s to -0.5s relative to STIM-ON.
    *   Stimulation: +0.5s to +4.0s.
3.  **Normalization:** Apply dB or log-ratio normalization to both conditions.
4.  **Contrasting:** Compute **Mean TFR(FOT) - Mean TFR(IFNFN)**.

---

## 8. Quality Metrics & Troubleshooting
*   **Good Data:** SNR > 3 dB, Phase Locking > 0.2.
*   **Troubleshooting Noise:**
    *   *High 50Hz:* Check GND (FPZ) gel.
    *   *Flat Lines:* Check hardware channel mapping.
    *   *Drift:* Re-clean and re-gel the electrode site.
