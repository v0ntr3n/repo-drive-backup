# repo-drive-backup

GitHub Actions workflow to pack the repository (excluding `.git/` and `.github/`) into a ZIP and upload it to Google Drive.

## Required Repository Secrets

Add these 4 secrets under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
| --- | --- |
| `GDRIVE_CLIENT_ID` | OAuth 2.0 Client ID from [Cloud Console Credentials](https://console.cloud.google.com/apis/credentials) (`...apps.googleusercontent.com`) |
| `GDRIVE_CLIENT_SECRET` | OAuth 2.0 Client Secret (`GOCSPX-...`) |
| `GDRIVE_REFRESH_TOKEN` | Refresh token from [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) (`1//0g...`, not `ya29...`) |
| `GDRIVE_FOLDER_ID` | Google Drive folder ID (no slashes or `?usp=...`) |

## Usage

Once the 4 secrets are saved, go to **Actions → Sync Repo ZIP to Drive → Run workflow** to trigger your first upload.

Each run also automatically deletes all previously completed workflow runs to keep CI history clean.