"""
Module for interacting with Google Drive API to download EEG data files.

This module provides functionality to authenticate with Google Drive using
OAuth2, list files in a specific folder, and download a random file.
It follows the repository's strict determinism and safety guidelines.
"""

import io
import logging
import random
import sys
from pathlib import Path
from typing import Optional

import yaml

# Add the project root to sys.path to allow 'from src...' imports
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from src.utils.paths import ROOT_DIR, CONFIG_DIR, RAW_DATA_DIR

# --- GLOBAL ENFORCEMENT RULES ---
RANDOM_SEED: int = 42
random.seed(RANDOM_SEED)

# --- LOGGING CONFIGURATION ---
logger = logging.getLogger(__name__)

# --- CONSTANTS ---
SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "google_drive.yaml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads the Google Drive configuration from a YAML file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        A dictionary containing the configuration settings.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
    """
    if not config_path.exists():
        logger.error("Configuration file not found: %s", config_path)
        raise FileNotFoundError(f"Configuration file {config_path} not found.")

    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def authenticate_drive(
    credentials_path: Path, token_path: Path
) -> Credentials:
    """
    Authenticates with Google Drive using OAuth2.

    If a valid token file exists, it will be reused. Otherwise, it will
    open a browser window for user authentication.

    Args:
        credentials_path: Path to the credentials.json file from Google Cloud.
        token_path: Path where the authentication token will be stored.

    Returns:
        The authenticated Google API credentials object.
    """
    creds: Optional[Credentials] = None

    # Load existing token if it exists
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh or create new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google Drive token.")
            creds.refresh(Request())
        else:
            logger.info("Starting new Google Drive authentication flow.")
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Credentials file {credentials_path} not found. "
                    "Please download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the token for subsequent runs
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


def download_random_file_from_drive(
    folder_id: str,
    download_dir: Path,
    credentials_path: Path,
    token_path: Path,
) -> Path:
    """
    Downloads a random file from a specified Google Drive folder.

    Args:
        folder_id: The ID of the Google Drive folder.
        download_dir: The directory where the file will be saved.
        credentials_path: Path to the credentials.json file.
        token_path: Path to the token.json file.

    Returns:
        The path to the downloaded file.

    Raises:
        RuntimeError: If no files are found in the specified folder.
    """
    creds = authenticate_drive(credentials_path, token_path)
    service = build("drive", "v3", credentials=creds)

    # List files in the folder
    query: str = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query, fields="files(id, name)", pageSize=100
    ).execute()
    files = results.get("files", [])

    if not files:
        logger.error("No files found in Drive folder ID: %s", folder_id)
        raise RuntimeError(f"No files found in Drive folder {folder_id}")

    # Select a random file (deterministic due to RANDOM_SEED)
    selected_file = random.choice(files)
    file_id: str = selected_file["id"]
    file_name: str = selected_file["name"]
    output_path: Path = download_dir / file_name

    logger.info("Downloading random file: %s (ID: %s)", file_name, file_id)

    # Perform the download
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.info("Download progress: %d%%", int(status.progress() * 100))

    # Save to disk
    download_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(fh.getvalue())

    logger.info("Successfully downloaded to %s", output_path)
    return output_path


if __name__ == "__main__":
    # Setup basic logging for standalone execution
    logging.basicConfig(level=logging.INFO)

    try:
        config = load_config()
        
        # Resolve paths relative to ROOT_DIR if they are not absolute
        def resolve_path(p: str) -> Path:
            path = Path(p)
            return path if path.is_absolute() else ROOT_DIR / path

        downloaded_file = download_random_file_from_drive(
            folder_id=config["folder_id"],
            download_dir=resolve_path(config["download_dir"]),
            credentials_path=resolve_path(config["credentials_path"]),
            token_path=resolve_path(config["token_path"]),
        )
        logger.info("Process completed. File saved at: %s", downloaded_file)
    except Exception as e:
        logger.exception("An error occurred during Google Drive interaction: %s", e)

# Suggested unit test:
# 1. Mock the Google Drive API service.
# 2. Provide a mock file list.
# 3. Verify that the random selection is consistent with RANDOM_SEED=42.
# 4. Mock the download stream and verify file write.
