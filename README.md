# F2H VBS EEG Software Suite

This repository provides a comprehensive software suite designed for the F2Heal vibrotactile device. It enables seamless synchronization between tactile stimulation and EEG data acquisition, offering tools for both real-time measurement and post-session analysis.


## Installation

To use this software, clone the GitHub repository.

Install the Python MNE libraries in a conda environment (e.g., named `f2heal`):

    $ conda create --channel=conda-forge --strict-channel-priority --name=f2heal mne
    $ conda activate f2heal

## Software Usage

For detailed usage, configuration, and command-line arguments, see the [User Manual](docs/Usage.md).

## Hardware setup

For details on the typical hardware setup, see [Hardware](docs/Hardware.md)

## Data repository

Data from previous recordings is stored on Google Drive in MNE FIF format. Contact the project administrators for access to this drive
