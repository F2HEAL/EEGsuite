# 🛠 Admin Guide: Google Drive Integration Maintenance

This document provides technical instructions for administrators to maintain the Google Drive API integration used for automated data retrieval in EEGsuite.

---

## 🔐 Google Cloud Console Configuration

The integration relies on a Google Cloud Project (currently `f2hdatashare`). This project is managed under the Google account: **f2heald@gmail.com**.

If you need to manage or recreate this setup, follow these steps:

### 1. OAuth Consent Screen & Test Users
Since the app is not verified by Google, it must remain in **Testing** mode.
1.  Go to [APIs & Services > OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).
2.  **User Type**: External (unless you have a Google Workspace organization).
3.  **Publishing Status**: Keep as **Testing**. If pushed to "Production," the app will require a full security audit by Google.
4.  **Test Users**: This is the most common maintenance task.
    *   Only users added to this list can authenticate.
    *   Click **+ ADD USERS** to authorize new research staff.
    *   Enter their Gmail/Workspace email address and save.

### 2. Enabling APIs
Ensure the **Google Drive API** is enabled for the project:
1.  Go to [Enabled APIs & Services](https://console.cloud.google.com/apis/dashboard).
2.  If not listed, click **+ ENABLE APIS AND SERVICES** and search for "Google Drive API".

### 3. Managing Credentials
If the `config/credentials.json` is lost or the project changes:
1.  Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials).
2.  Click **Create Credentials > OAuth client ID**.
3.  Select **Desktop App** as the application type.
4.  Download the JSON file and rename it to `credentials.json`.
5.  Place it in the `config/` directory of the repository.

---

## 🔑 Token Management

### How it works
- **`credentials.json`**: The "identity" of the application (Client ID and Secret).
- **`token.json`**: The user's specific "session" (Access and Refresh tokens). It is generated automatically after the first successful browser login.

### Resetting Authentication
If a user is having persistent authentication issues:
1.  Delete `config/token.json`.
2.  Run the script again (`python src/utils/google_drive.py`).
3.  This will force a fresh browser login and re-authorization.

---

## ⚠️ Troubleshooting Common Issues

### "Access blocked: App has not completed the Google verification process"
- **Cause**: The user's email is not in the **Test Users** list.
- **Fix**: Add the email in the OAuth consent screen settings (see Section 1).

### "Google hasn't verified this app" (Warning Page)
- **Cause**: Expected behavior for development/internal projects.
- **Fix**: Instruct users to click **Advanced > Go to [App Name] (unsafe)**.

### "Token has been expired or revoked"
- **Cause**: The user changed their password or revoked access manually.
- **Fix**: Delete `config/token.json` and re-authenticate.

---

## 🛡 Security & Best Practices

1.  **Scope Discipline**: The script uses `https://www.googleapis.com/auth/drive.readonly`. Do **not** increase this scope to full "drive" access unless strictly necessary for writing files.
2.  **File Protection**:
    *   `credentials.json` and `token.json` contain sensitive secrets.
    *   **NEVER** commit `token.json` to the git repository (it is excluded by `.gitignore`).
    *   `credentials.json` should only be shared via secure channels within the research team.

---

## 🏥 Health Check Manual Procedures

### Quick Health Check (Automated)

For a fast automated health check, run:

```bash
# From project root
python src/utils/check_google_drive_health.py
```

This utility will:
- Verify credentials file exists and is valid
- Check token file status
- Test Google Drive API connectivity
- List accessible files

**Expected Output**:
```
=== Google Drive Integration Health Check ===

[OK] Credentials file valid: config/credentials.json
[OK] Token file valid: config/token.json
[OK] Google Drive API is accessible
[OK] Drive contains N items (tested)
[OK] Recently accessed files:
  1. Example Doc (application/vnd.google-apps.document)
  ...

=== Health Check Complete ===

[OK] Google Drive integration is properly configured
```

---

### Manual Health Check Procedures

Use these manual procedures to verify the Google Drive integration step-by-step. These are useful for detailed diagnostics when the automated check reports issues.

### Prerequisites (Both Windows 11 & Linux)

1.  **Navigate to EEGsuite root directory:**
    ```bash
    cd /path/to/EEGsuite
    ```

2.  **Verify credentials file exists:**
    - `config/credentials.json` must be present and readable
    - If missing: Re-generate credentials in Google Cloud Console (see Section 3 above)

3.  **Verify required packages are installed (Windows):**
    ```powershell
    pip list | Select-String -Pattern google
    ```
    Should show: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
    
    If missing: `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`

    **Verify required packages are installed (Linux):**
    ```bash
    pip list | grep -i google
    ```
    Should show: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
    
    If missing: `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`

---

### Health Check Procedure: **Windows 11**

#### Step 1: Verify Credentials File Readability
```powershell
# Open PowerShell and navigate to project root
cd D:\F2H_code\GH\EEGsuite

# Check credentials file exists and is valid JSON
Get-Content config\credentials.json | ConvertFrom-Json
```

**Expected Output**: Should display JSON object with fields: `client_id`, `client_secret`, `auth_uri`, `token_uri`

**If fails**: Credentials file is corrupted or missing. Contact project administrator.

---

#### Step 2: Check Token Status
```powershell
# If token.json exists, verify it's valid JSON
if (Test-Path config\token.json) {
    Get-Content config\token.json | ConvertFrom-Json
    Write-Host "Token exists and is readable"
} else {
    Write-Host "No token found. First login required."
}
```

**Expected Output**: Either displays token JSON with `access_token` and `refresh_token`, or notification that first login is needed.

**If token file is corrupted**: Delete it and proceed to Step 3.

---

#### Step 3: Test Google Drive API Connectivity (Manual)
```powershell
# Create a Python test script in the project directory
@"
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
config_dir = Path('config')

# Load credentials
with open(config_dir / 'credentials.json') as f:
    client_config = json.load(f)

# Check for existing token
token_path = config_dir / 'token.json'
credentials = None

if token_path.exists():
    credentials = Credentials.from_authorized_user_file(token_path, SCOPES)

# Refresh or create token
if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
        print('[OK] Refreshing token...')
        credentials.refresh(Request())
    else:
        print('[INFO] Initiating new OAuth flow...')
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(token_path, 'w') as f:
            f.write(credentials.to_json())
        print('[OK] New token saved to config/token.json')

# Test API
print('[INFO] Testing Google Drive API...')
service = build('drive', 'v3', credentials=credentials)
results = service.files().list(pageSize=1, fields='files(id, name)').execute()
print('[OK] Google Drive API is accessible')
print(f'[OK] Drive contains {len(results.get("files", []))} items (tested via pagination)')
"@ | Out-File -FilePath test_gdrive.py

# Run the test
python test_gdrive.py
```

**Expected Output**:
```
[OK] Google Drive API is accessible
[OK] Drive contains N items (tested via pagination)
```

**If browser popup appears**: Click "Advanced" then "Go to app (unsafe)" to authorize.

**If fails with "Access blocked"**: 
- The test user email must be added to the OAuth Consent Screen test users list (see Section 1, Step 4).

**If fails with "Token expired"**: 
- Delete `config/token.json` and re-run; you will be prompted to log in again.

---

#### Step 4: Verify Drive Folder Permissions
```powershell
# Run this Python snippet to list accessible files
@"
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
token_path = Path('config/token.json')

credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
service = build('drive', 'v3', credentials=credentials)

# List recent files
results = service.files().list(pageSize=10, fields='files(id, name, mimeType)').execute()
files = results.get('files', [])

if files:
    print('[OK] Successfully listed files from Google Drive:')
    for f in files:
        print(f"  - {f['name']} ({f['mimeType']})")
else:
    print('[WARNING] No files found. Check folder permissions.')
"@ | Out-File -FilePath check_drive_files.py

python check_drive_files.py
```

**Expected Output**: List of 10 most recent files with names and types.

**If empty**: Verify the Drive folder permissions or check that files exist in the shared Drive.

---

#### Step 5: Cleanup
```powershell
# Remove temporary test scripts
Remove-Item -Path test_gdrive.py, check_drive_files.py -ErrorAction SilentlyContinue
Write-Host "Health check complete."
```

---

### Health Check Procedure: **Linux**

#### Step 1: Verify Credentials File Readability
```bash
# Navigate to project root
cd /path/to/EEGsuite

# Check credentials file exists and is valid JSON
python3 -c "import json; json.load(open('config/credentials.json'))" && echo "[OK] Credentials file is valid JSON" || echo "[ERROR] Credentials file is invalid"
```

**Expected Output**: `[OK] Credentials file is valid JSON`

**If fails**: Credentials file is corrupted or missing. Contact project administrator.

---

#### Step 2: Check Token Status
```bash
# If token.json exists, verify it's valid JSON
if [ -f config/token.json ]; then
    python3 -c "import json; json.load(open('config/token.json'))" && echo "[OK] Token exists and is readable" || echo "[ERROR] Token file is corrupted"
else
    echo "[INFO] No token found. First login required."
fi
```

**Expected Output**: Either `[OK] Token exists and is readable` or notification that first login is needed.

**If token file is corrupted**: Delete and proceed to Step 3.

---

#### Step 3: Test Google Drive API Connectivity (Manual)
```bash
# Create a Python test script
cat > test_gdrive.py << 'EOF'
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
config_dir = Path('config')

# Load credentials
with open(config_dir / 'credentials.json') as f:
    client_config = json.load(f)

# Check for existing token
token_path = config_dir / 'token.json'
credentials = None

if token_path.exists():
    credentials = Credentials.from_authorized_user_file(token_path, SCOPES)

# Refresh or create token
if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
        print('[OK] Refreshing token...')
        credentials.refresh(Request())
    else:
        print('[INFO] Initiating new OAuth flow...')
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(token_path, 'w') as f:
            f.write(credentials.to_json())
        print('[OK] New token saved to config/token.json')

# Test API
print('[INFO] Testing Google Drive API...')
service = build('drive', 'v3', credentials=credentials)
results = service.files().list(pageSize=1, fields='files(id, name)').execute()
print('[OK] Google Drive API is accessible')
print(f'[OK] Drive contains items (tested via pagination)')
EOF

# Run the test
python3 test_gdrive.py
```

**Expected Output**:
```
[OK] Google Drive API is accessible
[OK] Drive contains items (tested via pagination)
```

**If browser popup appears**: Authorize the application by clicking through the OAuth consent screen.

**If fails with "Access blocked"**:
- The test user email must be added to the OAuth Consent Screen test users list (see Section 1, Step 4).
- This is the most common failure point for new users.

**If fails with "Token expired"**:
- Delete `config/token.json` and re-run; you will be prompted to log in again.

---

#### Step 4: Verify Drive Folder Permissions
```bash
# Run this Python snippet to list accessible files
cat > check_drive_files.py << 'EOF'
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
token_path = Path('config/token.json')

credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
service = build('drive', 'v3', credentials=credentials)

# List recent files
results = service.files().list(pageSize=10, fields='files(id, name, mimeType)').execute()
files = results.get('files', [])

if files:
    print('[OK] Successfully listed files from Google Drive:')
    for f in files:
        print(f"  - {f['name']} ({f['mimeType']})")
else:
    print('[WARNING] No files found. Check folder permissions.')
EOF

python3 check_drive_files.py
```

**Expected Output**: List of 10 most recent files with names and types.

**If empty**: Verify the Drive folder permissions or check that files exist in the shared Drive.

---

#### Step 5: Cleanup
```bash
# Remove temporary test scripts
rm -f test_gdrive.py check_drive_files.py
echo "Health check complete."
```

---

## 🔍 Quick Troubleshooting Reference

| Error | Platform | Cause | Fix |
|-------|----------|-------|-----|
| `credentials.json` not found | Both | Configuration missing | Obtain from project admin or re-generate in Google Cloud Console |
| `token.json` corrupted | Both | File corruption | Delete token and re-authenticate |
| "Access blocked: App has not completed..." | Both | Email not in test users | Add email to OAuth Consent Screen in Google Cloud Console |
| "Token has expired" | Both | Token revoked or password changed | Delete `config/token.json` and re-authenticate |
| Empty file list in Step 4 | Both | No Drive access or empty Drive | Verify shared Drive permissions or check Drive contents |

---

## 📋 Health Check Verification Checklist

Use this checklist after completing the health check procedure:

- [ ] Credentials file (`config/credentials.json`) is readable and valid JSON
- [ ] Token file (`config/token.json`) is present and readable (or created after first login)
- [ ] Google Drive API test completed successfully (Step 3)
- [ ] File list returns N items (Step 4)
- [ ] No "Access blocked" errors encountered
- [ ] No "Token expired" errors encountered

**Status**: If all items are checked, Google Drive integration is properly configured.
