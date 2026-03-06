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
