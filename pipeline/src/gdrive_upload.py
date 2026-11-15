"""Optional Google Drive uploader for one already-downloaded pilot file.

Uses the least-privilege drive.file OAuth scope. It never asks for a Google
password, never logs OAuth tokens, verifies the uploaded bytes, and never
deletes a local file unless the user explicitly confirms at the prompt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DEFAULT_CLIENT_FILE = Path(__file__).resolve().parents[1] / "config" / "oauth" / "google_oauth_client.json"
APPDATA = Path(os.environ.get("APPDATA", Path.home()))
DEFAULT_TOKEN_FILE = APPDATA / "FlareUp" / "google_drive_token.json"


def upload_and_verify(local_file: Path, client_file: Path, token_file: Path, folder_id: str | None) -> dict:
    if not local_file.is_file():
        raise FileNotFoundError(f"Local upload file not found: {local_file}")
    if not client_file.is_file():
        raise FileNotFoundError(
            "OAuth client file is missing. Create a Google OAuth Desktop client and save it at: "
            f"{client_file}. Do not put passwords in this file."
        )

    try:
        Request = importlib.import_module("google.auth.transport.requests").Request
        Credentials = importlib.import_module("google.oauth2.credentials").Credentials
        InstalledAppFlow = importlib.import_module("google_auth_oauthlib.flow").InstalledAppFlow
        build = importlib.import_module("googleapiclient.discovery").build
        MediaFileUpload = importlib.import_module("googleapiclient.http").MediaFileUpload
    except ImportError as error:
        raise RuntimeError(
            "Optional Google Drive packages are not installed. Review requirements-gdrive.txt first."
        ) from error

    token_file.parent.mkdir(parents=True, exist_ok=True)
    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        # Print the OAuth URL for the user to open; no browser profile or
        # browser cookies are read by this program.
        credentials = flow.run_local_server(port=0, open_browser=False)
    token_file.write_text(credentials.to_json(), encoding="utf-8")

    before_size = local_file.stat().st_size
    before_md5 = hashlib.md5(local_file.read_bytes()).hexdigest()
    metadata = {"name": local_file.name}
    if folder_id:
        metadata["parents"] = [folder_id]
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    created = service.files().create(
        body=metadata,
        media_body=MediaFileUpload(str(local_file), resumable=True),
        fields="id,name,size,md5Checksum,mimeType,webViewLink",
    ).execute()
    verified = service.files().get(
        fileId=created["id"],
        fields="id,name,size,md5Checksum,mimeType,webViewLink",
    ).execute()
    remote_size = int(verified.get("size", -1))
    remote_md5 = verified.get("md5Checksum", "").lower()
    is_verified = remote_size == before_size and remote_md5 == before_md5
    result = {
        "file_id": verified.get("id"),
        "name": verified.get("name"),
        "size_bytes": remote_size,
        "md5_verified": bool(remote_md5 and remote_md5 == before_md5),
        "size_verified": remote_size == before_size,
        "upload_verified": is_verified,
        "web_view_link": verified.get("webViewLink"),
        "local_file": str(local_file),
        "local_file_removed": False,
        "oauth_scope": SCOPES[0],
    }
    if not is_verified:
        raise RuntimeError("Drive upload was created, but size/checksum verification failed; local file was retained.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload and verify one file in Google Drive (optional).")
    parser.add_argument("file", type=Path)
    parser.add_argument("--client-file", type=Path, default=DEFAULT_CLIENT_FILE)
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--folder-id")
    parser.add_argument(
        "--remove-local-after-verified",
        action="store_true",
        help="Offer removal only after Drive size and MD5 verification; requires typing an exact confirmation.",
    )
    args = parser.parse_args()
    result = upload_and_verify(args.file.resolve(), args.client_file.resolve(), args.token_file, args.folder_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.remove_local_after_verified:
        confirmation = input(
            f"Upload verified. Type REMOVE LOCAL FILE to permanently remove {args.file.resolve()}: "
        )
        if confirmation == "REMOVE LOCAL FILE":
            args.file.resolve().unlink()
            result["local_file_removed"] = True
            print("Local file removed after explicit confirmation.")
        else:
            print("Local file retained; confirmation did not match.")


if __name__ == "__main__":
    main()
