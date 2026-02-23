import os
from pathlib import Path
from typing import Optional

# Tell your team members to run these commands once on their machines:
# Windows (PowerShell):
# [System.Environment]::SetEnvironmentVariable('EEG_CLOUD_ROOT', 'G:\Shared drives\YourDriveName', 'User')

# e.g. PS C:\Users\pieter> [System.Environment]::SetEnvironmentVariable('EEG_CLOUD_ROOT', 'G:\My Drive\SharedData', 'User')

# Mac/Linux (Terminal):
# echo 'export EEG_CLOUD_ROOT="/path/to/google/drive"' >> ~/.bashrc (or ~/.zshrc)

# --- THE PATH ANCHOR ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# --- STANDARDIZED DIRECTORIES ---
# Local (GitHub tracked)
CONFIG_DIR = ROOT_DIR / "config"

# These will be initialized by set_cloud_root()
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
REPORT_DIR: Path = ROOT_DIR / "reports"
LOG_DIR: Path = ROOT_DIR / "logs"


def set_cloud_root(new_root: Optional[Path] = None) -> None:
    """
    Sets the root directory for data, logs, and reports.
    If new_root is not provided, it attempts to use EEG_CLOUD_ROOT env var,
    falling back to ROOT_DIR. Validates that the path is accessible.

    Args:
        new_root: Optional path to set as the cloud root.
    """
    global DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORT_DIR, LOG_DIR

    if new_root:
        candidate_root = Path(new_root).resolve()
    else:
        cloud_env = os.getenv("EEG_CLOUD_ROOT")
        candidate_root = Path(cloud_env).resolve() if cloud_env else ROOT_DIR

    # Validate accessibility (especially for network/external drives)
    try:
        # Check if the anchor (e.g., 'G:\') exists and is accessible
        if not Path(candidate_root.anchor).exists():
            raise OSError(f"Drive {candidate_root.anchor} is not accessible")
        cloud_root = candidate_root
    except (OSError, ValueError) as e:
        # If logging isn't setup yet, we use a simple print here as a last resort,
        # but usually main.py handles the logging setup after this.
        print(f"⚠️ Warning: Requested root {candidate_root} is unreachable ({e}).")
        print(f"⚠️ Falling back to local project root: {ROOT_DIR}")
        cloud_root = ROOT_DIR

    DATA_DIR = cloud_root / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    REPORT_DIR = cloud_root / "reports"
    LOG_DIR = cloud_root / "logs"


# Initialize with defaults or environment variable
set_cloud_root()


# Ensure Cloud directories exist before the app starts
def initialize_directories():
    """Creates the necessary directory structure if it doesn't exist."""
    for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORT_DIR, LOG_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
