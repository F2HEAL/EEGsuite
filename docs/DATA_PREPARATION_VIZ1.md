# EEG Data Preparation & Visualization Analysis (`viz1_prep_html.py`)

This document analyzes how the `viz1_prep_html.py` script prepares raw EEG data for analysis. The script serves as a robust preprocessing and reporting pipeline for data recorded via Brainflow (FreeEEG32).

## 1. Data Ingestion
- **Source**: Reads raw Brainflow CSV files (transposed to match MNE structure).
- **Scaling**: Converts signal from Volts (Brainflow default) to **microVolts ($\mu V$)** by applying a $1 \times 10^{-6}$ factor.
- **MNE Integration**: Wraps the raw numpy arrays into an `mne.io.RawArray` object with specified channel names and a sampling rate of **1000 Hz**.

## 2. Channel & Montage Setup
- **Standard Montages**: If a montage (e.g., `standard_1020`) is defined in the YAML config, it is applied to the data.
- **Dummy Montage**: If no montage is specified, the script creates a "dummy" montage where all channel coordinates are set to zero. This is a clever workaround to allow the `pyprep` library to initialize without failing, even if spatial information is missing.

## 3. Preprocessing Pipelines
The script implements two distinct paths for data cleaning, chosen automatically based on the availability of a montage.

### Path A: Full PREP Pipeline (with Montage)
Uses the `pyprep.PrepPipeline` to implement the "Preprocessing Pipeline" (Bigdely-Shamlo et al., 2015).
- **Line Noise Removal**: Removes 50 Hz and all harmonics up to the Nyquist frequency.
- **Robust Referencing**: Iteratively finds a clean average reference while excluding "noisy" channels.
- **Bad Channel Detection**: Uses **RANSAC** (Random Sample Consensus) to identify channels that do not correlate well with their neighbors, alongside SNR and deviation checks.
- **Interpolation**: Automatically interpolates identified bad channels using spherical splines.

### Path B: SimplePrep (Fallback without Montage)
A simplified pipeline used when spatial coordinates are unavailable.
- **Notch Filtering**: Explicitly removes line noise at 50, 100, 150, 200, and 250 Hz.
- **Bandpass Filtering**: Applies a zero-phase FIR filter from **1.5 Hz to 250 Hz**.
- **Average Referencing**: Applies a standard global average reference (`set_eeg_reference("average")`).

## 4. Visualization & Reporting
The script generates a comprehensive HTML report (`HTMLReport`) containing several layers of data verification:

- **Channel Quality**: Tables detailing which channels were marked as bad by various criteria (NaN, Flat, Correlation, etc.).
- **Timeseries**: 10-second and 1-minute snapshots of the cleaned signals.
- **Power Spectral Density (PSD)**:
    - Global overview (0-100 Hz).
    - Per-channel plots to identify local artifacts or specific frequency peaks.
    - **Topographic Grouping**: Aggregates PSDs by coronal (e.g., all 'F' channels) and sagittal lines (e.g., all 'z' channels) to check for regional noise patterns.
- **Spectrograms (TFR)**:
    - Uses **Morlet Wavelets** to compute Time-Frequency Representations.
    - Optimized for memory by decimating the output to **100 Hz**.
    - Helps identify transient artifacts or time-varying neural oscillations.

## Summary of Constraints
| Step | Detail |
| :--- | :--- |
| **Sampling Rate** | Fixed at 1000 Hz |
| **Filtering** | 1.5 - 250 Hz (default) |
| **Notch** | 50 Hz harmonics |
| **Reference** | Robust PREP or Global Average |
| **Output** | HTML Report + PNG Assets |
