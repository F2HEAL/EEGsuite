# Preprocessing Comparison: Cleaning vs. Contrast Analysis

This document compares the data preparation strategies of `viz1_prep_html.py` (documented in `DATA_PREPARATION_VIZ1.md`) and the `tfr_contrast.py` pipeline.

## 1. Philosophical Difference
- **`viz1_prep_html.py` (Heavy Cleaning)**: Aims to create a "perfect" version of a single recording by identifying and correcting bad channels, removing global noise, and robustly referencing.
- **`tfr_contrast.py` (Artifact Cancellation)**: Aims to isolate a specific signal by subtracting a "noise template" (IFNFN) from the "signal + noise" recording (FOT). It assumes that consistent artifacts (like EM motor noise) will be shared across both conditions and thus "canceled out" by the contrast.

## 2. Comparison Table

| Feature | `viz1_prep_html.py` (PREP) | `tfr_contrast.py` (Pipeline) |
| :--- | :--- | :--- |
| **Input Type** | Raw Brainflow CSV (Scaling needed) | MNE `.fif.gz` (Assumed pre-scaled) |
| **Filtering** | 1.5 - 250 Hz Bandpass | Configurable (Default 5 - 250 Hz) |
| **Notch Filter** | 50Hz harmonics up to Nyquist | Explicitly defined list (e.g., [50, 100]) |
| **Bad Channels** | Detected via RANSAC and interpolated | No interpolation; relies on Contrast to clean |
| **Referencing** | Robust Average or standard Average | **Virtual Channels (Laplacian)** |
| **Cleaning Focus** | Statistical outliers, flat channels, SNR | EM Artifact cancellation via condition subtraction |
| **Normalization** | Signal-level (Z-score not applied) | **TFR-level Baseline Normalization** (LogRatio/dB) |

## 3. Preprocessing Steps in `tfr_contrast.py`

### 1. Data Ingestion & Virtual Channels
Unlike the standard PREP pipeline, `tfr_contrast` allows for the creation of **Virtual Channels** (e.g., Weighted Laplacians) before any filtering. This is a form of spatial preprocessing that enhances local signal-to-noise ratios (SNR) by subtracting weighted averages of surrounding electrodes.

### 2. Basic Filtering
It applies standard zero-phase FIR bandpass and notch filters. It is less aggressive than `pyprep` because it avoids the iterative robust referencing stage to maintain the original phase and amplitude relationship between the FOT and IFNFN recordings—critical for successful subtraction.

### 3. Contrast as "Cleaning"
The most powerful "cleaning" step in `tfr_contrast` is the subtraction itself:
$$Contrast_{TFR} = FOT_{TFR} - IFNFN_{TFR}$$
This step cancels:
- **EM Artifacts**: Constant electromagnetic noise from the vibration motors.
- **Environmental Noise**: Constant 50Hz or lab-equipment noise shared by both blocks.
- **Background Brain Activity**: Non-task related oscillations that were consistent across both sessions.

### 4. TFR Baseline Normalization
While `viz1_prep` cleans the time-series, `tfr_contrast` normalizes the **Time-Frequency Representation**. It uses a pre-stimulus baseline window (e.g., -1.0 to -0.5s) to convert raw power into a decibel (dB) or Log-Ratio scale. This accounts for the 1/f power distribution and channel-specific impedance differences.

## 4. Conclusion: When to use which?
- Use **`viz1_prep_html.py`** for an initial deep dive into a recording to verify electrode contact and see if any channels are statistically "broken" or need interpolation.
- Use **`tfr_contrast.py`** for the final scientific result. It prioritizes the **comparative difference** between stimulation and control, using the control session as a biological/technical filter rather than relying on mathematical interpolation.
