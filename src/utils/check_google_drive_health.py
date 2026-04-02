#!/usr/bin/env python3
"""
Google Drive Integration Health Check Utility

This script verifies that the Google Drive API integration is properly
configured and functional. Run this script to diagnose issues with
Google Drive authentication and connectivity.

Usage:
    python check_google_drive_health.py
"""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
import sys


SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / 'config'


def print_status(status: str, message: str) -> None:
    """Print colored status message."""
    icons = {
        'OK': '[OK]',
        'ERROR': '[ERROR]',
        'INFO': '[INFO]',
        'WARNING': '[WARNING]'
    }
    print(f"{icons.get(status, status)} {message}")


def check_credentials_file() -> bool:
    """Verify credentials.json exists and is valid."""
    cred_path = CONFIG_DIR / 'credentials.json'
    try:
        if not cred_path.exists():
            print_status('ERROR', f"Credentials file not found: {cred_path}")
            return False
        
        with open(cred_path) as f:
            cred_config = json.load(f)
        
        # Handle both formats: direct OAuth config and "installed" app format
        if 'installed' in cred_config:
            cred_config = cred_config['installed']
        
        required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
        if not all(field in cred_config for field in required_fields):
            missing = [f for f in required_fields if f not in cred_config]
            print_status('ERROR', f"Credentials file missing required fields: {missing}")
            return False
        
        print_status('OK', f"Credentials file valid: {cred_path}")
        return True
    except json.JSONDecodeError:
        print_status('ERROR', "Credentials file is not valid JSON")
        return False
    except Exception as e:
        print_status('ERROR', f"Error reading credentials: {e}")
        return False


def check_token_file() -> bool:
    """Check if token file exists and is readable."""
    token_path = CONFIG_DIR / 'token.json'
    
    if not token_path.exists():
        print_status('INFO', "No token file found. First authentication required.")
        return True
    
    try:
        with open(token_path) as f:
            token_data = json.load(f)
        
        if 'access_token' not in token_data:
            print_status('WARNING', "Token file missing access_token")
            return False
        
        print_status('OK', f"Token file valid: {token_path}")
        return True
    except json.JSONDecodeError:
        print_status('ERROR', "Token file is corrupted. Delete and re-authenticate.")
        return False
    except Exception as e:
        print_status('ERROR', f"Error reading token: {e}")
        return False


def obtain_credentials() -> Credentials | None:
    """Load or refresh credentials."""
    with open(CONFIG_DIR / 'credentials.json') as f:
        client_config = json.load(f)
    
    # Handle both formats: direct OAuth config and "installed" app format
    if 'installed' in client_config:
        client_config = {'installed': client_config['installed']}
    
    token_path = CONFIG_DIR / 'token.json'
    credentials = None
    
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print_status('WARNING', f"Could not load token: {e}")
            return None
    
    # Refresh or re-authenticate
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print_status('INFO', "Token expired. Attempting refresh...")
            try:
                credentials.refresh(Request())
                with open(token_path, 'w') as f:
                    f.write(credentials.to_json())
                print_status('OK', "Token refreshed successfully")
            except Exception as e:
                print_status('WARNING', f"Token refresh failed: {e}")
                print_status('INFO', "Initiating new OAuth flow...")
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                credentials = flow.run_local_server(port=0)
                with open(token_path, 'w') as f:
                    f.write(credentials.to_json())
                print_status('OK', "New token saved")
        else:
            print_status('INFO', "Initiating new OAuth flow...")
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            credentials = flow.run_local_server(port=0)
            with open(token_path, 'w') as f:
                f.write(credentials.to_json())
            print_status('OK', "New token saved")
    
    return credentials


def test_api_connectivity(credentials: Credentials) -> bool:
    """Test Google Drive API connectivity."""
    try:
        print_status('INFO', "Testing Google Drive API...")
        service = build('drive', 'v3', credentials=credentials)
        results = service.files().list(
            pageSize=1,
            fields='files(id, name)'
        ).execute()
        
        print_status('OK', "Google Drive API is accessible")
        files = results.get('files', [])
        print_status('OK', f"Drive contains {len(files)} items (tested)")
        return True
    except Exception as e:
        print_status('ERROR', f"API test failed: {e}")
        return False


def list_drive_files(credentials: Credentials, limit: int = 10) -> bool:
    """List recent files from Google Drive."""
    try:
        service = build('drive', 'v3', credentials=credentials)
        results = service.files().list(
            pageSize=limit,
            fields='files(id, name, mimeType)'
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            print_status('OK', f"Recently accessed files:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f['name']} ({f['mimeType']})")
            return True
        else:
            print_status('WARNING', "No files found. Check Drive access permissions.")
            return False
    except Exception as e:
        print_status('ERROR', f"Could not list files: {e}")
        return False


def main() -> int:
    """Run complete health check."""
    print("\n=== Google Drive Integration Health Check ===\n")
    
    # Step 1: Check credentials file
    if not check_credentials_file():
        return 1
    
    # Step 2: Check token file
    if not check_token_file():
        print_status('WARNING', "Token file check failed")
    
    # Step 3: Obtain valid credentials
    print()
    credentials = obtain_credentials()
    if not credentials:
        print_status('ERROR', "Could not obtain valid credentials")
        return 1
    
    # Step 4: Test API connectivity
    print()
    if not test_api_connectivity(credentials):
        return 1
    
    # Step 5: List files
    print()
    list_drive_files(credentials)
    
    print("\n=== Health Check Complete ===\n")
    print_status('OK', "Google Drive integration is properly configured")
    return 0


if __name__ == '__main__':
    sys.exit(main())
