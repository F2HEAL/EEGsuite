# 📊 TFR Contrast Analysis (Section 9 Pipeline)

The `tfr_contrast.py` module implements a high-precision Time-Frequency Representation (TFR) analysis pipeline designed to isolate neural responses from strong electromagnetic (EM) interference.

---

## 🔍 Overview: The EM Noise Challenge

In EEG studies involving vibrotactile stimulators (tactors), the device often radiates electromagnetic noise at the exact same frequency as the tactile stimulation (e.g., 22 Hz). This creates a significant problem:

1.  **Inseparability**: The EEG electrodes pick up both the **neural response** to touch and the **tactor's EM artifact**.
2.  **Frequency Overlap**: Because they occur at the same frequency, traditional filtering cannot separate them.
3.  **PSD Limitation**: Power Spectral Density (PSD) can tell you *if* a frequency is present, but it averages over time, mixing baseline and stimulation periods and making it impossible to see *when* or *how* the signal changes.

### 💡 The Solution: Condition Contrasting
The pipeline solves this by recording two identical conditions that differ only by physical tactile contact:
*   **FOT (Finger-On-Tactor)**: Subject's finger is touching the tactor. (Neural Response + EM Noise + Background)
*   **IFNFN (In-Field-No-Feeling-Nipple)**: Tactor is active at the same location/power, but the subject's finger is NOT touching it. (EM Noise + Background)

By subtracting the IFNFN condition from the FOT condition ($FOT - IFNFN$), the EM noise and background activity cancel out, leaving only the **pure neural response**.

---

## 🛠 The 4-Step Pipeline

The module processes the EEG data through four distinct stages:

1.  **Full Time–Frequency Transform**: Uses Morlet wavelets to decompose the continuous signal into power across both time and frequency.
2.  **Epoching**: Data is sliced into "trials" around the stimulation triggers, including safety margins.
    ![Epoch Time Window](assets/TFR%20step2%20Epoch%20Time%20Window.png)
3.  **Baseline Normalization**: Each trial is normalized against its own pre-stimulus rest period (supports dB, log-ratio, or percent change).
4.  **Condition Contrasting**: The normalized IFNFN trials are subtracted from the FOT trials to produce the final contrast map.

---

## 🏷 Marker System

The system uses a condition-aware marking scheme to distinguish between trial types:

| Condition | Rest (00) | Stim ON (01) | Stim OFF (11) |
| :--- | :--- | :--- | :--- |
| **FOT** (1xx) | `100` | `101` | `111` |
| **IFNFN** (2xx) | `200` | `201` | `211` |

**Backward Compatibility**: The script also supports legacy markers (`0` for rest, `1` for ON, `11` for OFF). If new markers are not found, it falls back to analyzing single-condition data (Steps 1–3 only).

---

## 🚀 Usage

### Standalone Command
You can run the analysis directly on raw CSV files:

```bash
python -m src.analysis.offline.tfr_contrast \
    --fot  data/raw/SUBJECT_FOT.csv \
    --ifnfn data/raw/SUBJECT_IFNFN.csv \
    --config config/analysis/contrast_offline.yaml
```

### Main CLI Integration
If integrated into `main.py`, use the `contrast` subcommand:

```bash
python -m src.main contrast --fot FOT.csv --ifnfn IFNFN.csv
```

### Single Condition Mode
To analyze a single file without contrasting (useful for checking signal quality):

```bash
python -m src.analysis.offline.tfr_contrast --fot data/raw/SINGLE_FILE.csv --ifnfn data/raw/SINGLE_FILE.csv
```

---

## 📋 Configuration (`TFRContrastConfig`)

The pipeline parameters are managed via a dataclass and can be overridden by a YAML file:

*   **Frequencies**: Range (e.g., 5–100 Hz) and number of steps.
*   **Time Window**: Pre-stimulus and post-stimulus margins.
*   **Normalization**: Mode (dB, percent, etc.) and baseline window.
*   **Montage**: Supports standard 10–20 layouts (defaulting to `freg9`).

---

## 📈 Outputs

The module generates a comprehensive **HTML Report** containing:
*   **Channel Response Summary**: Numerical detection of **SSSEP** (Steady-State Somatosensory Evoked Potentials) and **Beta ERD** (Event-Related Desynchronization) with Cohen's *d* effect sizes.
*   **TFR Heatmaps**: 2D plots of Power vs. Frequency vs. Time for FOT, IFNFN, and the Contrast.
*   **Condition Comparisons**: Side-by-side visualizations of the raw and processed states for every channel.
*   **Band Time-courses**: Linear plots showing how specific frequency bands (Stim Freq, Beta, Gamma) evolve during the trial.
*   **EM Cancellation Metrics**: Estimation of how much electromagnetic artifact was removed during subtraction.
