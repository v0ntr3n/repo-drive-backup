#!/usr/bin/env python3
"""Zip repository contents and upload to a Google Drive folder using OAuth2 refresh token."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path


def get_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise SystemExit(f"Missing required environment variable/secret: {name}")
    return val


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OAuth token refresh failed ({e.code}): {err_body}")
    token = payload.get("access_token")
    if not token:
        raise SystemExit("OAuth response did not include access_token")
    return token


def build_zip(repo_root: Path, out_zip: Path) -> int:
    count = 0
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(repo_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(repo_root)
            if rel.parts[0] in {".git", ".github"}:
                continue
            zf.write(p, rel.as_posix())
            count += 1
    return count


def find_existing_file(token: str, folder_id: str, filename: str) -> str | None:
    safe_name = filename.replace("'", "\\'")
    q = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
    params = urllib.parse.urlencode({"q": q, "fields": "files(id,name)", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
    req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files?{params}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        files = json.loads(resp.read().decode("utf-8")).get("files", [])
    return files[0]["id"] if files else None


def upload_zip(token: str, folder_id: str, filename: str, zip_path: Path, overwrite: bool) -> dict:
    existing_id = find_existing_file(token, folder_id, filename) if overwrite else None
    metadata = {"name": filename} if existing_id else {"name": filename, "parents": [folder_id]}

    boundary = f"----gdrive-{uuid.uuid4().hex}"
    zip_bytes = zip_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8") + zip_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    if existing_id:
        url = f"https://www.googleapis.com/upload/drive/v3/files/{existing_id}?uploadType=multipart&supportsAllDrives=true"
        method = "PATCH"
    else:
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
        method = "POST"

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Drive upload failed ({e.code}): {err_body}")


def main() -> None:
    client_id = get_env("GDRIVE_CLIENT_ID")
    client_secret = get_env("GDRIVE_CLIENT_SECRET")
    refresh_token = get_env("GDRIVE_REFRESH_TOKEN")
    folder_id = get_env("GDRIVE_FOLDER_ID")

    repo_name = os.environ.get("GITHUB_REPOSITORY", "repo").split("/")[-1]
    filename = os.environ.get("ZIP_FILENAME", "").strip() or f"{repo_name}.zip"
    if not filename.endswith(".zip"):
        filename += ".zip"
    overwrite = os.environ.get("OVERWRITE_EXISTING", "true").lower() == "true"

    zip_path = Path("/tmp") / filename
    count = build_zip(Path.cwd(), zip_path)
    print(f"Packed {count} files into {zip_path} ({zip_path.stat().st_size} bytes)")

    token = get_access_token(client_id, client_secret, refresh_token)
    res = upload_zip(token, folder_id, filename, zip_path, overwrite)
    print(f"Uploaded to Google Drive: id={res.get('id')} name={res.get('name')}")


if __name__ == "__main__":
    main()