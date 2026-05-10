# EEGsuite Usage Manual

This manual explains the usage of the unified command-line interface (CLI) for the EEGsuite software.

## Workflow

![Data Flow Structure](assets/EEGSuite%20overview.png)

A typical workflow would look as follows:
1. **LSLserver**: Start LSL server to stream the EEG data
2. **sweep**: Run the selected protocol and record EEG data to CSVs containing events
3. **convert**: Convert the CSV files to MNE FIF Raw objects
4. **analyze**: Analyze previously recorded data

When running **LSLserver** and **sweep** on different physical machines, you might need to [reconfigure your local firewall](lslw11firewall.md).

The main entry point for the software is `src/main.py`, which offers several subcommands.

## General Usage

    $ python -m src.main [command] [options]

## Available Commands

### 1. `LSLserver`

Starts the Lab Streaming Layer (LSL) server to read data from an EEG device and stream it via LSL.

#### Typical Command-Line Usage

    $ python -m src.main LSLserver -m config/montages/freg9.yaml  -c config/hardware/freeeeg.yaml

* `-c, --config`: Path to the EEG hardware configuration YAML file. (**Required**)
* `-m, --montage`: Path to a montage YAML file containing channel names. (Optional)

Note: An optional montage file will set the LSL stream metadata (Channel names, ...), but this is currently not used by sweep. The montage is also supplied during analysis for that purpose. 


### 2. `sweep`

Runs the Sweep Protocol for data recording. It connects to the LSL server and executes the requested protocol setup by interfacing with the vibrotactile device. Recorded data is saved to the data directory in CSV format, with the legacy event markers. Use the convert utility to turn it into an MNE FIF Raw file.

For more details see [Sweep](Sweep.md)

#### Typical Command-Line Usage

    $ python -m src.main sweep -d config/hardware/vbs_only.yaml -p config/protocols/sweep_tfr.yaml


* `-p, --protocol`: Path to the protocol configuration file.  (**Required**)
* `-d, --device`: Path to the hardware configuration file. (**Required**)

### 3. `analyze`
Analyzes a single recorded MNE RAW EEG file and generates an offline visual analysis report in the report directory

#### Typical Command-Line Usage

    $ python -m src.main analyze -f data/recording.fif -c config/analysis.yaml -s 10.0 -d 30.0

* `-f, --file`: Path to the MNE RAW file to analyze. (**Required**)
* `-c, --config`: Path to the analysis YAML configuration file. (Optional; defaults to a generic offline analysis configuration).
* `-s, --start`: Start time for analysis in seconds. (Optional; default: `0.0`).
* `-d, --duration`: Duration of the data to analyze in seconds. (Optional; default: `60.0`).
* `-v, --verbose`: Enables verbose output. (Optional)

### 4. `analyze_contrast`
Runs a Time-Frequency Representation (TFR) Contrast Analysis pipeline. It compares recorded data between two conditions: FOT (Finger-On-Tactor) and IFNFN (In-Field-Not-Feeling-Nipple).

For details on this method see [tfr_contrast_presentation1.odp](tfr_contrast_presentation1.odp)

#### Typical Command-Line Usage

    $ python -m src.main analyze_contrast --fot ${DATADIR}/processed/260502-1123_None_c6_f37_v100_eeg.fif.gz --ifnfn ${DATADIR}/260502-1143_None_c5_f37_v100_eeg.fif.gz --config config/analysis/contrast_37hz.yaml --output /tmp/report/1123-1143


* `--fot`: Path to the MNE RAW file for the FOT condition. (**Required**)
* `--ifnfn`: Path to the MNE RAW file for the IFNFN condition. (**Required**)
* `-c, --config`: Path to the TFR analysis YAML configuration. (Optional)
* `-o, --output`: Output directory where the generated report will be saved. (Optional; default: `reports`).
* `-s, --stimfreq`: Stimulation frequency in Hz. (Optional)
* `--export-csv`: Extracts and exports the analyzed TFR data to a CSV format. (Optional)

#### Marker system

The system uses a condition-aware marking scheme to distinguish between trial types:

| Condition       | Rest (00) | Stim ON (01) | Stim OFF (11) |
|:----------------|:----------|:-------------|:--------------|
| **FOT** (1xx)   | `100`     | `101`        | `111`         |
| **IFNFN** (2xx) | `200`     | `201`        | `211`         |

**Backward Compatibility**: The script also supports legacy markers (`0` for rest, `1` for ON, `11` for OFF). If new markers are not found, it falls back to analyzing single-condition data (Steps 1–3 only).


### 5. `convert`
Converts EEG data stored in a generic CSV format into an MNE RAW format file.

#### Typical Command-Line Usage

    $ python src/main.py convert -f data/raw_data.csv -c config/montages/freg9.yaml -o data/raw/

* `-f, --file`: Path to the input CSV file. (**Required**)
* `-c, --config`: Path to the hardware/channel configuration file. (**Required**)
* `-o, --output-dir`: Output directory for the converted RAW file. (**Required**)
* `-v, --verbose`: Enables verbose output during conversion. (Optional)
