# EEGSuite: Technical Specification & System Capabilities

**Version:** 0.1.0  
**Document Date:** May 2026  
**Status:** Technical Specification  

---

## Executive Summary

**EEGSuite** is a comprehensive software platform designed for synchronized acquisition, processing, and analysis of electroencephalography (EEG) data in conjunction with vibrotactile stimulation. The system addresses a critical challenge in neuroscientific research: isolating neural responses from electromagnetic artifacts when measuring somatosensory evoked potentials in the presence of strong electromagnetic interference.

The suite provides end-to-end workflow support from real-time data streaming to advanced spectral analysis, with particular emphasis on reproducibility, determinism, and peer-review-ready scientific rigor. It is purpose-built for clinical neuroscience research investigating vibrotactile-induced neural activity, with direct application to Parkinson's disease research.

### Key Deliverables

- **Real-time EEG streaming** via Lab Streaming Layer (LSL) protocol
- **Synchronized vibrotactile stimulation** with precise temporal control
- **Automated preprocessing pipeline** with advanced artifact rejection
- **Time-Frequency-Representation (TFR) contrast analysis** for EM artifact suppression
- **Reproducible, publication-ready analysis reports**
- **Cross-platform compatibility** (Windows, Linux)

---

## 1. System Architecture

### 1.1 High-Level Overview

EEGSuite implements a **distributed acquisition and analysis architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        EEGSuite Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐     ┌─────────────┐  │
│  │   Hardware   │         │   LSL Stream │     │ Vibrotactile│  │
│  │ (FreeEEG32)  │────────▶│    Server    │◀────│  Device     │  │
│  └──────────────┘         └──────┬───────┘     └─────────────┘  │
│                                  │                                │
│                    ┌─────────────▼──────────────┐                │
│                    │   Data Acquisition        │                │
│                    │ (Sweep Protocol Handler)  │                │
│                    └─────────────┬──────────────┘                │
│                                  │                                │
│                    ┌─────────────▼──────────────┐                │
│                    │  CSV Data Conversion      │                │
│                    │  (FIF Format Generation)  │                │
│                    └─────────────┬──────────────┘                │
│                                  │                                │
│      ┌───────────────────────────┴────────────────────────┐     │
│      │                                                     │     │
│  ┌───▼──────────────┐  ┌────────────────────────────┐    │     │
│  │   Preprocessing  │  │  Analysis Pipelines:       │    │     │
│  │   (PREP/SimplePrep)  │  - Single-condition TFR   │    │     │
│  └────────────────┘  │  - Contrast (FOT vs IFNFN)  │    │     │
│                       │  - Power Spectral Density   │    │     │
│                       │  - Topographic Mapping      │    │     │
│                       └────────────┬─────────────────┘    │     │
│                                    │                      │     │
│                       ┌────────────▼──────────────┐       │     │
│                       │  Report Generation        │       │     │
│                       │  (HTML + Data Export)     │       │     │
│                       └───────────────────────────┘       │     │
│                                                            │     │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Modules

| Module | Responsibility |
|--------|-----------------|
| **streaming** | Lab Streaming Layer (LSL) server implementation; real-time EEG data acquisition from FreeEEG32 and device synchronization |
| **recording** | Sweep protocol executor; manages stimulus timing, event markers, and CSV file generation |
| **converting** | CSV-to-MNE converters; transforms raw data into standardized neuroscience formats |
| **analysis/offline** | Batch processing pipeline; implements TFR, contrast analysis, and preprocessing |
| **analysis/realtime** | Real-time visualization and monitoring (optional; extensible) |
| **utils** | Shared utilities; logging, configuration management, data validation |

---

## 2. Core Capabilities

### 2.1 Data Acquisition

**Real-Time Streaming via Lab Streaming Layer (LSL)**

- **Protocol:** LSL over TCP/UDP multicast
- **Sampling Rate:** 1000 Hz (configurable per hardware)
- **Channel Count:** Up to 32 channels (configurable)
- **Data Format:** Single-precision floating point (µV)
- **Latency:** <10 ms typical (depends on network)
- **Network Requirements:** Gigabit Ethernet recommended; UDP Multicast ports 16571–16604

**Features:**
- Multi-machine compatibility (acquisition node separate from control node)
- Automatic hardware detection and configuration
- Metadata streaming (channel names, montage information)
- Graceful handling of network interruptions

### 2.2 Synchronized Stimulation Protocol

**Sweep Protocol Implementation**

The system implements a structured experimental protocol with explicit artifact baseline capture:

**Phase 1: Calibration Baselines**

1. **Baseline 1 (Environmental Noise):** 10–60 seconds of ambient electrical noise measurement with vibrotactile device OFF
2. **Baseline 2 (EM Artifact Template):** Active stimulation at target frequency/amplitude with subject's finger NOT in contact (1 mm separation)
3. **Baseline 3 (Pre-Sweep Rest):** Subject in contact with tactor, stimulation OFF

**Phase 2: Sweep Sequence**

- Iterates through all combinations of:
  - **Channels:** Configurable stimulation locations
  - **Frequencies:** 1–100 Hz range (in 1 Hz increments or custom)
  - **Amplitudes:** 0–255 (arbitrary units, hardware-dependent)
- Each combination: Rest → Stimulation ON → Stimulation OFF
- Configurable timing for each phase
- Event markers embedded in EEG stream for trial synchronization

**Output:** Timestamped CSV files with synchronized EEG and event markers

### 2.3 Preprocessing Pipeline

**Dual-Path Design**

**Path A: Full PREP Pipeline** (when electrode montage provided)

Uses the Preprocessing Pipeline (Bigdely-Shamlo et al., 2015):
- **Line Noise Removal:** 50 Hz notch + harmonics up to Nyquist
- **Robust Average Reference:** Iteratively detects and excludes noisy channels
- **Bad Channel Detection:** Multi-criterion detection (RANSAC, SNR, deviation)
- **Interpolation:** Spherical spline interpolation of bad channels

**Path B: SimplePrep** (when montage unavailable)

- **Notch Filtering:** 50 Hz and harmonics (50, 100, 150, 200, 250 Hz)
- **Bandpass Filtering:** Zero-phase FIR 1.5–250 Hz
- **Average Referencing:** Global average reference

**Output:** Clean, artifact-rejected MNE Raw files ready for analysis

### 2.4 Advanced Analysis Capabilities

#### **Time-Frequency Representation (TFR)**

- **Wavelet Transform:** Complex Morlet wavelets
- **Frequency Coverage:** 1–100 Hz (configurable)
- **Time Resolution:** Full stimulus-locked epochs (pre/post stimulus)
- **Memory Optimization:** Intelligent decimation (100 Hz output)
- **Output:** Time-frequency power maps per trial and condition

#### **Condition Contrast Analysis**

Proprietary algorithm addressing the **EM Artifact Problem**:

**Problem Statement:** When measuring neural responses to vibrotactile stimulation, the EEG electrodes pick up both:
1. Neural somatosensory evoked response (our target signal)
2. Electromagnetic radiation from the stimulator at the same frequency (artifact)

**Solution:** Record two physically identical conditions differing only in tactile contact:

- **FOT (Finger-On-Tactor):** Subject touching the stimulator → Neural response + EM artifact + background
- **IFNFN (In-Field-Not-Feeling-Nipple):** Subject's finger 1 mm away → EM artifact + background only

**Contrast Map:** FOT − IFNFN = **Pure Neural Response** (EM artifacts cancel out)

**Implementation:**
1. Compute TFR for both conditions
2. Epoch around stimulation triggers
3. Automatic peak-to-peak rejection (default: 200 µV threshold)
4. Normalize each trial to its pre-stimulus baseline (dB, log-ratio, or percent change)
5. Subtract condition-averaged normalized TFRs

**Marker System (Backward Compatible):**

| Condition | Rest (00) | Stim ON (01) | Stim OFF (11) |
|-----------|-----------|-------------|---------------|
| FOT (1xx) | `100`     | `101`       | `111`         |
| IFNFN (2xx) | `200`   | `201`       | `211`         |

Legacy markers (`0`, `1`, `11`) supported for single-condition analysis.

#### **Artifact & Epoch Rejection**

- **Peak-to-Peak (P2P) Rejection:** Configurable threshold (default: 200 µV); automatic removal of epochs with excessive amplitude excursions
- **Purpose:** Remove eye blinks, muscle twitches, Parkinsonian tremors
- **Logging:** Console reports number of clean vs. rejected epochs

#### **Spectral Analysis**

- **Power Spectral Density (PSD):** Welch's method (configurable window/overlap)
- **Topographic Mapping:** 2D scalp plots of power distribution
- **Frequency Bands:** Alpha, beta, theta, gamma (configurable)
- **Regional Aggregation:** Averaging by coronal/sagittal electrode lines

---

## 3. Technical Specifications

### 3.1 Software Requirements

| Requirement | Specification |
|-------------|----------------|
| **Python** | ≥ 3.11 |
| **OS Compatibility** | Windows (7+), Linux (Ubuntu 20.04+) |
| **Core Dependencies** | MNE 1.x, BrainFlow, PyLSL, PyPrep, SciPy, NumPy |
| **Package Manager** | Conda (recommended) or pip |

### 3.2 Hardware Requirements

**Acquisition Hardware (Minimum)**

- **EEG Device:** FreeEEG32 (32-channel biosignal amplifier)
- **Sampling Rate:** 1000 Hz (configurable)
- **ADC Resolution:** 24-bit (device-dependent)
- **Input Range:** ±250 mV typical
- **Impedance:** >100 MΩ (standard EEG electrodes)

**Stimulation Device**

- **Vibrotactile Tactor:** Voice-coil-based (frequency range 1–100 Hz)
- **Control Interface:** USB / Serial
- **Amplitude Range:** 0–255 arbitrary units
- **Frequency Resolution:** 1 Hz (configurable)

**Computing Platform (Recommended)**

- **Acquisition Node:** Laptop with USB 3.0 + Ethernet (for LSL streaming)
  - Minimum: 2-core CPU, 4 GB RAM
  - Recommended: 4+ cores, 8+ GB RAM
- **Control Node:** Same or separate system for protocol execution
- **Network:** Dedicated Gigabit Ethernet switch (for low-latency LSL)

### 3.3 Data Format Specifications

**Raw CSV Input**

- **Structure:** Channels as columns, samples as rows (transposed from BrainFlow default)
- **Data Type:** Float32 (microvolts)
- **Sampling Rate:** 1000 Hz (assumed)
- **Event Markers:** Integer column indicating trial phase/condition

**MNE FIF Output (HDF5-like Container)**

- **Format:** MNE Raw + Event information
- **Compression:** Optional gzip
- **Metadata Preserved:**
  - Channel names/locations
  - Montage information
  - Sampling rate & hardware parameters
  - Preprocessing history

**Report HTML**

- **Content:** Interactive visualizations (time series, PSD, TFR, topomaps)
- **Browser Compatibility:** Modern browsers (Chrome, Firefox, Safari)
- **Size:** Typically 5–50 MB per report (depends on data length)

---

## 4. Data Processing Pipeline

### 4.1 Step-by-Step Workflow

```
INPUT: Raw hardware data
  ↓
[1. LSL Streaming] → Real-time acquisition from FreeEEG32
  ↓
[2. Sweep Protocol] → Execute stimulus protocol, record markers
  ↓
[3. CSV Files] → Raw data + event timing (data/raw/)
  ↓
[4. Convert] → Transform to MNE Raw FIF format
  ↓
[5. Preprocessing] → PREP or SimplePrep pipeline
  ↓
[6. Analysis] → Choose analysis mode:
  │
  ├─→ [Single Condition] → TFR + PSD + Report
  │
  └─→ [Contrast] → FOT vs IFNFN subtraction
        ↓
        Epoch + P2P Rejection
        ↓
        Normalize (dB/log/percent)
        ↓
        Subtract conditions
  ↓
OUTPUT: HTML report + CSV exports
```

### 4.2 Configuration Management

All parameters specified via YAML files:

- **Hardware Config:** `config/hardware/*.yaml`
  - Sampling rate, channel count, impedance ranges
  - Serial port/USB connection parameters
  
- **Montage Config:** `config/montages/*.yaml`
  - Channel name mapping (FreeEEG pins to 10-20 locations)
  - Reference electrode designation
  - Weighted Laplacian coefficients (if applicable)

- **Protocol Config:** `config/protocols/*.yaml`
  - Stimulus sequence (channel, frequency, amplitude combinations)
  - Timing parameters (rest duration, stim duration)
  - Baseline configuration

- **Analysis Config:** `config/analysis/*.yaml`
  - Filter specifications (lowcut, highcut, order)
  - Wavelet parameters (frequency range, n_cycles)
  - Baseline normalization method
  - Artifact rejection thresholds

---

## 5. Key Features & Strengths

### 5.1 Artifact Management

**Electromagnetic Interference Suppression**

The FOT/IFNFN contrast method is a novel approach to handling EM artifacts that are impossible to remove via conventional filtering. This is particularly valuable for:
- Vibrotactile neuroscience research
- Deep brain stimulation (DBS) combined with EEG
- Repetitive transcranial magnetic stimulation (rTMS) studies

**Automatic Rejection Mechanisms**

- Peak-to-peak amplitude thresholds
- RANSAC-based bad channel detection
- SNR and deviation-based channel quality metrics
- Configurable rejection parameters

### 5.2 Reproducibility & Determinism

**By Design:**
- Explicit random seed control (RANDOM_SEED = 42)
- No implicit randomness in data processing
- All output deterministic given identical input
- Git-friendly configuration files

**Academic Standards:**
- Suitable for peer review and publication
- Transparent methodology
- Full parameter logging in metadata
- Cross-platform consistent results

### 5.3 Scientific Rigor

- **Signal Scaling:** Explicit microvolts (µV) throughout
- **Documentation:** Full docstrings with mathematical methods
- **Type Safety:** Complete Python type hints
- **Path Handling:** OS-independent pathlib (no hardcoded paths)
- **Logging:** Structured logging (no print() statements)

### 5.4 Extensibility

- Modular design (separate streaming, recording, analysis modules)
- Plugin architecture for custom analysis pipelines
- YAML-based configuration (no code changes for experiments)
- MNE-based analysis (integrates with broader MNE ecosystem)

---

## 6. Outputs & Deliverables

### 6.1 Real-Time Outputs

**LSL Stream**
- **Name:** `FreeEEG32` (configurable)
- **Type:** EEG
- **Channels:** 32 (or configured count)
- **Sampling Rate:** 1000 Hz
- **Format:** Float32 µV

### 6.2 Post-Acquisition Outputs

**Raw CSV Files** (in `data/raw/`)
- Columns: 32 EEG channels + 1 event marker column
- Rows: Timestamped samples (1000 per second)
- Example filename: `260502-1123_FREEEEG32_BOARD_c6_f37_v100.csv`

**Metadata File** (in `data/raw/`)
- Hardware parameters used during recording
- Protocol settings (channels, frequencies, amplitudes)
- Baseline durations and markers
- Example: `260502-1123_metadata.txt`

### 6.3 Processed Outputs

**MNE Raw FIF Files** (in `data/processed/`)
- Standardized neuroscience format
- Full metadata embedded
- Ready for third-party analysis tools
- Compressed with gzip (`.fif.gz`)

**Analysis Reports** (in `reports/`)

**Preprocessing Report:**
- Time series visualizations (10-sec and 60-sec windows)
- Power spectral density (global + per-channel)
- Topographic power maps (2D scalp plots)
- Channel quality assessment (bad channels detected)
- Spectrograms (time-frequency via Morlet wavelets)
- HTML format, fully interactive

**Single-Condition TFR Report:**
- Stimulus-locked time-frequency power maps
- Baseline-normalized representation (dB or percent change)
- Per-frequency band power time courses
- Artifact rejection summary (epochs rejected, reason)

**Contrast Report:**
- Side-by-side TFR maps (FOT, IFNFN, Contrast)
- Difference strength (statistical maps if N>1)
- Channel-by-channel contrast strength
- Artifact rejection summary (FOT vs. IFNFN rejection rates)
- EM artifact suppression evidence

### 6.4 Data Export

**CSV Exports (optional)**

Command-line flag `--export-csv` extracts:
- Epoched TFR data (time × frequency × channel × condition)
- Averaged power per frequency band
- Topographic scalp maps (if applicable)
- Suitable for import into MATLAB, R, or statistical software

---

## 7. Use Cases

### 7.1 Primary Research Application

**Vibrotactile-Induced Somatosensory Responses (Parkinson's Disease)**

- Measure EEG responses to vibrotactile stimulation at variable frequencies/amplitudes
- Isolate pure neural response via FOT/IFNFN contrast
- Quantify response strength and frequency tuning
- Assess therapeutic potential of vibrotactile interventions

### 7.2 Secondary Applications

**Deep Brain Stimulation (DBS) + EEG Research**
- Record cortical responses to subcortical stimulation
- Use FOT/IFNFN paradigm for artifact suppression
- Characterize closed-loop DBS response dynamics

**Somatosensory Neuroscience Studies**
- Frequency selectivity of somatosensory cortex
- Topographic mapping of receptive fields
- Population-level coherence analysis

**Device Development & Testing**
- Characterize vibrotactile tactor frequency response
- Measure EM emissions at different stimulus parameters
- Verify device safety (artifact profile assessment)

---

## 8. Performance Characteristics

### 8.1 Processing Speed

| Task | Duration | Dataset Size |
|------|----------|--------------|
| **CSV → MNE Conversion** | <1 sec | 1 min of 32-ch EEG |
| **Preprocessing (PREP)** | 10–30 sec | 10 min raw EEG |
| **Single-Condition TFR** | 5–15 sec | 10 min, 32 channels |
| **Contrast TFR** | 15–45 sec | 2 × 10 min files |
| **HTML Report Generation** | 5–10 sec | Complete pipeline output |

### 8.2 Memory Usage

| Component | Memory |
|-----------|--------|
| **Raw EEG (1 min, 32-ch, 1000 Hz)** | ~8 MB |
| **Preprocessed (same)** | ~16 MB |
| **TFR (1–100 Hz, 100 Hz decimation)** | ~50 MB |
| **Peak Memory (full pipeline)** | ~500 MB typical (depends on data length) |

### 8.3 Scalability

- **Horizontal:** Multi-machine LSL streaming supported (up to ~10 inlet streams on gigabit Ethernet)
- **Vertical:** Single-machine processing: tested up to 2 hours of continuous 32-channel EEG
- **Parallelization:** Batch analysis of multiple files (external job scheduler recommended)

---

## 9. Quality Assurance

### 9.1 Testing & Validation

- **Unit Tests:** Provided for core mathematical functions (signal filtering, TFR, contrast)
- **Integration Tests:** End-to-end workflow validation with synthetic data
- **Regression Tests:** Performance/output stability across versions

### 9.2 Logging & Diagnostics

- **Structured Logging:** Python logging module (INFO, DEBUG, WARNING, ERROR levels)
- **Audit Trail:** Preprocessing history embedded in MNE metadata
- **Error Reporting:** Detailed error messages with context (line numbers, parameter values)
- **Debug Mode:** Verbose output available via `-v` flag

### 9.3 Determinism Verification

- Identical outputs for identical inputs (bit-level reproducibility)
- Random seeds explicitly set and logged
- No floating-point accumulation errors (tests included)
- Cross-platform validation (Windows vs. Linux)

---

## 10. Integration with External Tools

### 10.1 Ecosystem Compatibility

- **MNE-Python:** Full integration via MNE Raw objects
- **MATLAB:** Data export to CSV; import via `readtable()`
- **R:** CSV export; import via `read.csv()` or `data.table::fread()`
- **EEGLAB:** MNE FIF files compatible via plugins
- **FieldTrip:** MNE Raw objects convertible to FieldTrip format

### 10.2 Data Sharing

- **MNE FIF Format:** Industry standard for neuroscience data
- **BIDS Compliance:** Structure compatible with Brain Imaging Data Structure (optional tooling)
- **Google Drive Integration:** Metadata support for cloud storage workflows

---

## 11. Limitations & Considerations

### 11.1 Known Limitations

1. **Sampling Rate:** Fixed at 1000 Hz (hardware-dependent; configurable at build time)
2. **Channel Count:** Limited to 32 channels (FreeEEG32 hardware ceiling; extensible with multi-device setup)
3. **Montage Dependency:** Full PREP pipeline requires valid electrode coordinates; SimplePrep fallback available
4. **EM Artifact Method:** Requires two-condition protocol (FOT + IFNFN); not applicable to single-condition studies

### 11.2 Environmental Requirements

1. **Electromagnetic Shielding:** Recommend Faraday cage or shielded room (not mandatory)
2. **Network Isolation:** Dedicated Ethernet switch recommended for LSL stability
3. **Power Management:** Battery power for acquisition node recommended (eliminates 50/60 Hz mains coupling)

### 11.3 Data Privacy & Security

- **Google Drive Integration:** Requires OAuth token (credentials.json, token.json)
- **No Built-in Encryption:** Data at rest unencrypted; recommend external encryption
- **Compliance:** Users responsible for HIPAA/GDPR compliance if using patient data

---

## 12. Deployment & Maintenance

### 12.1 Installation

**Conda (Recommended)**
```bash
conda create -c conda-forge -n f2heal mne
conda activate f2heal
cd EEGsuite
pip install -e .
```

**Manual Setup**
```bash
git clone https://github.com/F2HEAL/EEGsuite.git
cd EEGsuite
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 12.2 Configuration

1. Create `config/hardware/freeeeg.yaml` with device parameters
2. Create `config/montages/your_montage.yaml` with channel mapping
3. Create `config/protocols/your_protocol.yaml` with stimulus sequence
4. Create `config/analysis/your_analysis.yaml` with processing parameters

### 12.3 Verification

Test LSL streaming:
```bash
python -m src.main LSLserver -c config/hardware/freeeeg.yaml -m config/montages/freg9.yaml
```

Test complete workflow:
```bash
python -m src.main sweep -p config/protocols/sweep_tfr.yaml -d config/hardware/vbs_only.yaml
python -m src.main convert -f data/raw/example.csv -c config/montages/freg9.yaml
python -m src.main analyze -f data/processed/example.fif -c config/analysis/default_offline.yaml
```

---

## 13. Support & Documentation

### 13.1 Documentation Structure

- **[README.md](../README.md):** Quick start guide
- **[Usage.md](Usage.md):** Command-line reference & workflow
- **[Hardware.md](Hardware.md):** Hardware setup & schematic
- **[Montages.md](Montages.md):** Electrode placement & mapping
- **[Sweep.md](Sweep.md):** Protocol definition & markers
- **[PREPROCESSING_COMPARISON.md](PREPROCESSING_COMPARISON.md):** Preprocessing methods
- **[ANALYSIS_TFR_CONTRAST_pg.md](ANALYSIS_TFR_CONTRAST_pg.md):** Advanced analysis methods
- **[lslw11firewall.md](lslw11firewall.md):** Network configuration (Windows/Linux)

### 13.2 Academic References

Key citations for validation:

1. **Bigdely-Shamlo et al. (2015):** The PREP pipeline for EEG preprocessing
2. **Morlet Wavelet TFR:** Standard time-frequency decomposition method
3. **MNE-Python (Gramfort et al.):** Foundation for analysis infrastructure
4. **Lab Streaming Layer (LSL):** Real-time biomedical data streaming protocol

### 13.3 Community & Contribution

- **Repository:** [GitHub F2HEAL/EEGsuite](https://github.com/F2HEAL/EEGsuite)
- **Issue Tracking:** GitHub Issues for bug reports & feature requests
- **Contribution:** Pull requests welcome; follow Google Python Style Guide & copilot-instructions.md

---

## 14. Conclusion

**EEGSuite** is a production-ready software platform for high-precision EEG acquisition and analysis in vibrotactile neuroscience research. Its novel FOT/IFNFN contrast method addresses a fundamental challenge in the field: isolating neural responses in the presence of strong electromagnetic artifacts.

By combining real-time streaming, structured protocols, advanced preprocessing, and proprietary contrast analysis, EEGSuite enables rigorous, reproducible investigation of somatosensory cortical dynamics with direct clinical application to Parkinson's disease research.

The platform is designed for **scientific transparency**, **computational rigor**, and **peer-review readiness**, making it suitable for high-impact publication and cross-laboratory collaboration.

---

## Appendix A: Configuration Template

### Minimal Working Example

**`config/hardware/minimal.yaml`**
```yaml
device_type: FreeEEG32
sampling_rate: 1000
channels: 32
serial_port: /dev/ttyUSB0  # or COM3 on Windows
reference_channel: 0  # GND or physical reference
```

**`config/montages/minimal.yaml`**
```yaml
name: "Minimal 9-channel"
channels:
  - T7
  - C3
  - FC3
  - Cz
  - FC4
  - C4
  - T8
  - CP3
  - CP4
reference: "linked_ears"
```

**`config/protocols/minimal.yaml`**
```yaml
baselines:
  baseline_1: 10  # seconds, VHP OFF
  baseline_2: 10  # seconds, EM artifact template
  baseline_3: 5   # seconds, pre-sweep rest

sweep:
  channels: [1, 2, 3]
  frequencies: [10, 20, 30]
  amplitudes: [100, 150, 200]
  duration_on: 3  # seconds
  duration_off: 3  # seconds
```

**`config/analysis/minimal.yaml`**
```yaml
montage: "config/montages/minimal.yaml"
lowcut: 1.5
highcut: 250
notch_freq: 50

tfr:
  method: "morlet"
  freqs: [1, 100]
  n_cycles: 3
  
baseline_correction: "dB"
reject_p2p: 200  # µV
```

---

**Document Version:** 1.0  
**Last Updated:** May 2026  
**For questions or clarifications, contact the F2HEAL team.**
