import os
from pathlib import Path

# Tell your team members to run these commands once on their machines:
# Windows (PowerShell):
# [System.Environment]::SetEnvironmentVariable('EEG_CLOUD_ROOT', 'G:\Shared drives\YourDriveName', 'User')

# e.g. PS C:\Users\pieter> [System.Environment]::SetEnvironmentVariable('EEG_CLOUD_ROOT', 'G:\My Drive\SharedData', 'User')

# Mac/Linux (Terminal):
# echo 'export EEG_CLOUD_ROOT="/path/to/google/drive"' >> ~/.bashrc (or ~/.zshrc)

# --- THE PATH ANCHOR ---
# __file__ is 'src/utils/paths.py'
# .parent is 'src/utils/'
# .parent.parent is 'src/'
# .parent.parent.parent is the 'project_root/'
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# --- CLOUD DETECTION LOGIC ---
# Detect the environment variable 'EEG_CLOUD_ROOT'
# If it doesn't exist, it falls back to the local project_root
cloud_env = os.getenv("EEG_CLOUD_ROOT")

if cloud_env:
    # User has Google Drive mounted and the variable set
    CLOUD_ROOT = Path(cloud_env).resolve()
else:
    # Fallback for standalone/offline use
    CLOUD_ROOT = ROOT_DIR

# --- STANDARDIZED DIRECTORIES ---
# Local (GitHub tracked)
CONFIG_DIR = ROOT_DIR / "config"

# Cloud (Shared Drive)
DATA_DIR   = CLOUD_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORT_DIR = CLOUD_ROOT / "reports"
LOG_DIR    = CLOUD_ROOT / "logs"

# Ensure Cloud directories exist before the app starts
def initialize_directories():
    for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORT_DIR, LOG_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
