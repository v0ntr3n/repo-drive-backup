#!/usr/bin/env python3
"""Sync unpacked repository files and folders directly to a Google Drive folder using OAuth2."""

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
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
        raise SystemExit(f"OAuth token refresh failed ({e.code}): {e.read().decode('utf-8', errors='replace')}")
    token = payload.get("access_token")
    if not token:
        raise SystemExit("OAuth response did not include access_token")
    return token


def find_item(token: str, parent_id: str, name: str, mime_type: str | None = None) -> str | None:
    safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
    q = f"name = '{safe_name}' and '{parent_id}' in parents and trashed = false"
    if mime_type:
        q += f" and mimeType = '{mime_type}'"
    params = urllib.parse.urlencode(
        {"q": q, "fields": "files(id,name)", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
    )
    req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files?{params}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        files = json.loads(resp.read().decode("utf-8")).get("files", [])
    return files[0]["id"] if files else None


def ensure_folder(token: str, parent_id: str, name: str, cache: dict[tuple[str, str], str]) -> str:
    key = (parent_id, name)
    if key in cache:
        return cache[key]
    folder_mime = "application/vnd.google-apps.folder"
    existing = find_item(token, parent_id, name, folder_mime)
    if existing:
        cache[key] = existing
        return existing

    body = json.dumps({"name": name, "mimeType": folder_mime, "parents": [parent_id]}).encode("utf-8")
    req = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        fid = json.loads(resp.read().decode("utf-8"))["id"]
    cache[key] = fid
    return fid


def upload_file(token: str, parent_id: str, file_path: Path, overwrite: bool) -> dict:
    name = file_path.name
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    existing_id = find_item(token, parent_id, name) if overwrite else None
    metadata = {"name": name} if existing_id else {"name": name, "parents": [parent_id]}

    boundary = f"----gdrive-{uuid.uuid4().hex}"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

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
        raise SystemExit(f"Drive upload failed for {file_path} ({e.code}): {e.read().decode('utf-8', errors='replace')}")


def main() -> None:
    client_id = get_env("GDRIVE_CLIENT_ID")
    client_secret = get_env("GDRIVE_CLIENT_SECRET")
    refresh_token = get_env("GDRIVE_REFRESH_TOKEN")
    root_folder_id = get_env("GDRIVE_FOLDER_ID")
    overwrite = os.environ.get("OVERWRITE_EXISTING", "true").lower() == "true"

    token = get_access_token(client_id, client_secret, refresh_token)
    folder_cache: dict[tuple[str, str], str] = {}
    repo_root = Path.cwd()
    uploaded = 0

    for p in sorted(repo_root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_root)
        if rel.parts[0] in {".git", ".github"}:
            continue
        parent_id = root_folder_id
        for part in rel.parts[:-1]:
            parent_id = ensure_folder(token, parent_id, part, folder_cache)
        res = upload_file(token, parent_id, p, overwrite)
        uploaded += 1
        print(f"Uploaded {rel.as_posix()} -> id={res.get('id')}")

    print(f"Done: uploaded {uploaded} extracted file(s) to Drive folder {root_folder_id}")


if __name__ == "__main__":
    main()