"""Direct, one-file NASA PSI download through its short-lived S3 URL.

Pilot-safe: one file per invocation, inventory-gated, sequential, no cloud
upload, and never records or prints the temporary signed URL.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REPORTS_DIR

NASA_HOST = "psi.nasa.gov"
S3_HOST = "psi-repo-prod.s3.amazonaws.com"
DEFAULT_ID = "PSI-10"
DEFAULT_FILE = "PSI-10_Raw Data_21340A2_Comments.txt"
MAX_ENDPOINT_BYTES = 64 * 1024
CHUNK_BYTES = 64 * 1024
TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def load_inventory_entry(investigation_id: str, filename: str) -> tuple[dict, Path]:
    inventory_path = REPORTS_DIR / f"psi_file_inventory_{investigation_id}.json"
    if not inventory_path.is_file():
        raise FileNotFoundError(f"Inventory not found: {inventory_path}")
    report = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    investigations = [
        item for item in report.get("investigations", [])
        if item.get("investigation_id", "").upper() == investigation_id
    ]
    if not investigations:
        raise ValueError(f"{investigation_id} is absent from the PSI inventory.")
    records = [
        item for item in investigations[0].get("files", [])
        if item.get("file_name") == filename
    ]
    if len(records) != 1:
        raise ValueError(f"Expected one exact inventory record for {filename}; found {len(records)}.")
    entry = records[0]
    if entry.get("visible") is not True or entry.get("restricted") is True or entry.get("download_eligible") is not True:
        raise PermissionError("Inventory marks this item restricted, hidden, or not eligible; skipped.")
    if Path(filename).name != filename or not entry.get("storage_key"):
        raise ValueError("Unsafe filename or missing NASA storage key in inventory.")
    return entry, inventory_path


def nasa_download_endpoint(investigation_id: str, entry: dict) -> str:
    query = urlencode({"file": entry["file_name"], "version": entry.get("version") or 1, "redirect": "false"})
    return f"https://{NASA_HOST}/geode-py/ws/studies/{quote(investigation_id, safe='-')}/download?{query}"


def validate_signed_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != S3_HOST or not parsed.query:
        raise ValueError("NASA did not provide an HTTPS URL on the expected PSI S3 host.")
    return url


def signed_url_from_response(response_body: bytes) -> str:
    text = response_body.decode("utf-8", errors="replace")
    text = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&").replace("\\u0026", "&")
    pattern = re.compile(r"https://psi-repo-prod\.s3\.amazonaws\.com/[^\s\"'<>]+", re.IGNORECASE)
    for match in pattern.finditer(text):
        candidate = match.group(0).rstrip(",.;)}]")
        try:
            return validate_signed_url(candidate)
        except ValueError:
            continue
    raise ValueError("NASA endpoint response did not contain a valid PSI S3 URL; response was not saved.")


def get_signed_url(endpoint: str) -> tuple[str, int]:
    request = Request(endpoint, headers={"Accept": "application/json, text/plain, text/html, */*", "User-Agent": "Flare-Up-Data-Pipeline/1.0"})
    opener = build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as error:
        if error.code in {301, 302, 303, 307, 308}:
            location = error.headers.get("Location", "")
            if not location:
                raise ValueError(f"NASA returned HTTP {error.code} without a redirect URL.") from None
            from urllib.parse import urljoin
            return validate_signed_url(urljoin(endpoint, location)), error.code
        raise ValueError(f"NASA download endpoint returned HTTP {error.code}.") from None
    with response:
        status = response.status
        if not 200 <= status < 300:
            raise ValueError(f"NASA download endpoint returned HTTP {status}.")
        body = response.read(MAX_ENDPOINT_BYTES + 1)
    if len(body) > MAX_ENDPOINT_BYTES:
        raise ValueError("NASA endpoint response exceeded the small metadata-response limit.")
    return signed_url_from_response(body), status


def validate_content(path: Path, content_type: str, expected_size: int | None, file_extension: str | None = None) -> dict:
    size = path.stat().st_size
    if not size:
        raise ValueError("S3 returned an empty file.")
    if expected_size is not None and size != int(expected_size):
        raise ValueError(f"Downloaded size {size} does not match inventory size {expected_size}.")
    with path.open("rb") as source:
        sample = source.read(min(size, 4096)).lstrip().lower()
    if content_type in {"text/html", "application/xhtml+xml", "application/xml", "text/xml"}:
        raise ValueError(f"S3 response was an error document ({content_type}), not scientific data.")
    if sample.startswith((b"<!doctype html", b"<html", b"<?xml", b"<error")) or b"<accessdenied" in sample[:1024]:
        raise ValueError("Response body looks like an HTML/XML/access-denied error, not the requested file.")
    extension = (file_extension or path.suffix).lower()
    if extension == ".txt":
        try:
            path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("TXT payload is not valid UTF-8; retained for review, not marked valid.") from error
    if extension == ".pdf":
        try:
            import fitz
            with fitz.open(path) as document:
                if document.page_count < 1:
                    raise ValueError("PDF contains no pages.")
        except Exception as error:
            raise ValueError(f"PDF structure validation failed ({type(error).__name__}).") from None
    signatures = {
        ".pdf": (b"%PDF-", "pdf_signature"),
        ".jpg": (b"\xff\xd8\xff", "jpeg_signature"),
        ".jpeg": (b"\xff\xd8\xff", "jpeg_signature"),
        ".png": (b"\x89PNG\r\n\x1a\n", "png_signature"),
        ".zip": (b"PK\x03\x04", "zip_signature"),
    }
    if extension in signatures:
        signature, validation_kind = signatures[extension]
        with path.open("rb") as source:
            if not source.read(len(signature)).startswith(signature):
                raise ValueError(f"File does not match the expected {extension} signature.")
    else:
        validation_kind = "content_type_and_error_page_check"
    if extension == ".xlsx":
        from zipfile import BadZipFile, ZipFile
        try:
            with ZipFile(path) as archive:
                names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise ValueError("XLSX container lacks workbook structure.")
            validation_kind = "xlsx_container_structure"
        except BadZipFile as error:
            raise ValueError("XLSX file is not a valid ZIP-based workbook.") from error
    if extension == ".zip":
        from zipfile import BadZipFile, ZipFile
        try:
            with ZipFile(path) as archive:
                entries = len(archive.infolist())
            if entries == 0:
                raise ValueError("ZIP archive contains no entries.")
            validation_kind = "zip_directory_metadata_only"
        except BadZipFile as error:
            raise ValueError("ZIP archive central directory is invalid.") from error
    return {"valid": True, "content_type": content_type, "size_bytes": size, "method": validation_kind}


def parse_content_range(value: str | None):
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+)", value or "", re.IGNORECASE)
    return tuple(map(int, match.groups())) if match else None


def resume_candidate(target: Path, entry: dict):
    prefix, suffix = target.name + ".", ".partial.resume.json"
    for state_path in target.parent.iterdir():
        if not state_path.name.startswith(prefix) or not state_path.name.endswith(suffix):
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            partial_name = state["partial_name"]
            if Path(partial_name).name != partial_name:
                continue
            part_path = target.parent / partial_name
            if (part_path.is_file() and state.get("file_name") == target.name
                    and state.get("source_record_id") == entry.get("record_id")
                    and state.get("version") == entry.get("version")
                    and state.get("validator_kind") in {"etag", "last_modified"}
                    and state.get("validator_value") and part_path.stat().st_size > 0):
                return part_path, state, state_path
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return None


def create_partial(target: Path, entry: dict, endpoint: str, headers, total_size: int | None):
    etag = headers.get("ETag")
    modified = headers.get("Last-Modified")
    if etag and not etag.strip().startswith("W/"):
        validator_kind, validator_value = "etag", etag.strip()
    elif modified:
        validator_kind, validator_value = "last_modified", modified.strip()
    else:
        validator_kind, validator_value = None, None
    while True:
        part_path = target.with_name(f"{target.name}.{uuid.uuid4().hex}.partial")
        state_path = part_path.with_name(part_path.name + ".resume.json")
        try:
            with part_path.open("xb"):
                pass
            state = {"partial_name": part_path.name, "file_name": target.name,
                     "source_record_id": entry.get("record_id"), "version": entry.get("version"),
                     "source_tree_path": entry.get("relative_tree_path"), "endpoint": endpoint,
                     "total_size": total_size, "validator_kind": validator_kind,
                     "validator_value": validator_value}
            with state_path.open("x", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False)
            return part_path, state, state_path
        except FileExistsError:
            continue


def check_free_space(directory: Path, required_bytes: int | None) -> None:
    if required_bytes is None:
        return
    free_bytes = shutil.disk_usage(directory).free
    if free_bytes < required_bytes:
        raise OSError(f"Insufficient free disk space: need {required_bytes} bytes; have {free_bytes}.")


def _stream_body(response, destination, expected_body_bytes: int | None = None) -> int:
    received = 0
    with destination.open("ab") as output:
        while True:
            block = response.read(CHUNK_BYTES)
            if not block:
                break
            output.write(block)
            received += len(block)
        output.flush()
        os.fsync(output.fileno())
    if expected_body_bytes is not None and received != expected_body_bytes:
        raise OSError(f"Incomplete HTTP body: received {received} of {expected_body_bytes} bytes.")
    return received


def s3_response(signed_url: str, headers: dict):
    validate_signed_url(signed_url)
    request = Request(signed_url, headers={"User-Agent": "Flare-Up-Data-Pipeline/1.0",
                                           "Accept-Encoding": "identity", **headers})
    try:
        response = build_opener().open(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as error:
        if error.code == 416:
            return error
        raise ValueError(f"Signed S3 request returned HTTP {error.code}.") from None
    except URLError as error:
        raise ValueError(f"Signed S3 request failed at the network layer ({type(error.reason).__name__}).") from None
    if urlsplit(response.geturl()).hostname != S3_HOST:
        response.close()
        raise ValueError("S3 response redirected outside the approved storage host.")
    return response


def stream_download(signed_url: str, target: Path, entry: dict, endpoint: str):
    existing = resume_candidate(target, entry)
    if existing:
        part_path, state, state_path = existing
        offset = part_path.stat().st_size
        total = state.get("total_size")
        if total is None or offset < int(total):
            resume_headers = {"Range": f"bytes={offset}-",
                              "If-Range": state["validator_value"]}
            response = s3_response(signed_url, resume_headers)
            with response:
                range_info = parse_content_range(response.headers.get("Content-Range"))
                current_validator = response.headers.get("ETag" if state["validator_kind"] == "etag" else "Last-Modified")
                safe = (response.status == 206 and range_info is not None
                        and range_info[0] == offset and range_info[1] >= range_info[0]
                        and range_info[2] > range_info[1]
                        and (total is None or range_info[2] == int(total))
                        and current_validator is not None
                        and current_validator.strip() == state["validator_value"])
                if safe:
                    start, end, total = range_info
                    check_free_space(target.parent, total - offset)
                    expected_segment = end - start + 1
                    received = _stream_body(response, part_path, expected_segment)
                    state["total_size"] = total
                    with state_path.open("w", encoding="utf-8") as handle:
                        json.dump(state, handle, ensure_ascii=False)
                    if part_path.stat().st_size != total:
                        raise OSError(f"Resumed response supplied {received} bytes; file remains incomplete at {part_path.stat().st_size} of {total} bytes.")
                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    return part_path, part_path.stat().st_size, content_type, response.status, total, state_path
            # Unsafe or ignored range: preserve this partial and restart in a new file.

    response = s3_response(signed_url, {})
    with response:
        if response.status != 200:
            raise ValueError(f"Fresh S3 download returned HTTP {response.status}, expected 200.")
        raw_length = response.headers.get("Content-Length")
        try:
            content_length = int(raw_length) if raw_length is not None else None
        except ValueError:
            raise ValueError("S3 returned an invalid Content-Length.") from None
        inventory_size = entry.get("size_bytes")
        total = content_length if content_length is not None else (int(inventory_size) if inventory_size is not None else None)
        if content_length is not None and inventory_size is not None and content_length != int(inventory_size):
            raise ValueError(f"S3 Content-Length {content_length} does not match inventory size {inventory_size}.")
        check_free_space(target.parent, total)
        part_path, _state, state_path = create_partial(target, entry, endpoint, response.headers, total)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        received = _stream_body(response, part_path, content_length)
    byte_count = part_path.stat().st_size
    if total is not None and byte_count != total:
        raise OSError(f"Incomplete download: received {byte_count} of {total} bytes.")
    return part_path, byte_count, content_type, 200, total, state_path

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_one(investigation_id: str, filename: str) -> dict:
    entry, inventory_path = load_inventory_entry(investigation_id, filename)
    endpoint = nasa_download_endpoint(investigation_id, entry)
    output_dir = PROJECT_ROOT / "data" / "tmp" / "psi_downloads" / investigation_id
    tree_parts = [part for part in entry["relative_tree_path"].replace("\\", "/").split("/") if part]
    relative_parts = tree_parts[2:] if len(tree_parts) >= 3 else [filename]
    target = output_dir.joinpath(*relative_parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = REPORTS_DIR / "psi_http_download_manifest.jsonl"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing download: {target}")
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8-sig").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("investigation_id") == investigation_id and record.get("source_record_id") == entry.get("record_id"):
                raise FileExistsError("This NASA inventory record is already present in the verified HTTP manifest.")

    last_error: Exception | None = None
    endpoint_status = None
    content_type = ""
    download_status = None
    part_path = None
    state_path = None
    remote_size = None
    byte_count = 0
    stage = "requesting a fresh NASA download URL"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            stage = "requesting a fresh NASA download URL"
            signed_url, endpoint_status = get_signed_url(endpoint)
            validate_signed_url(signed_url)
            stage = "streaming the file from NASA storage"
            part_path, byte_count, content_type, download_status, remote_size, state_path = stream_download(
                signed_url, target, entry, endpoint
            )
            break
        except Exception as error:
            last_error = RuntimeError(f"{stage}: {type(error).__name__}: {error}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(1)
    else:
        raise RuntimeError(f"Direct HTTP download failed after {MAX_ATTEMPTS} bounded attempts: {last_error}") from None

    expected_size = remote_size if remote_size is not None else entry.get("size_bytes")
    validation = validate_content(part_path, content_type, expected_size, Path(filename).suffix)
    digest = sha256_file(part_path)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite a file created during download: {target}")
    # Hard-link creation is atomic and fails if the destination already exists.
    os.link(part_path, target)
    part_path.unlink()
    if state_path and state_path.exists():
        state_path.unlink()
    result = {
        "schema_version": "1.0",
        "investigation_id": investigation_id,
        "investigation_url": f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}",
        "nasa_download_endpoint": endpoint,
        "source_record_id": entry.get("record_id"),
        "storage_key": entry.get("storage_key"),
        "source_tree_path": entry.get("relative_tree_path"),
        "file_name": filename,
        "version": entry.get("version"),
        "inventory_size_bytes": entry.get("size_bytes"),
        "visible": entry.get("visible"),
        "restricted": entry.get("restricted"),
        "endpoint_status": endpoint_status,
        "s3_host": S3_HOST,
        "download_status": download_status,
        "saved_path": str(target),
        "size_bytes": byte_count,
        "sha256": digest,
        "validation": validation,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8", newline="\n") as manifest:
        manifest.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one inventory-listed PSI file using the NASA HTTP endpoint.")
    parser.add_argument("investigation_id", nargs="?", default=DEFAULT_ID)
    parser.add_argument("--file", default=DEFAULT_FILE, help="Exact filename from the existing PSI inventory.")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if not re.fullmatch(r"PSI-\d+", investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-10.")
    try:
        result = download_one(investigation_id, args.file)
    except Exception as error:
        raise SystemExit(f"HTTP_PILOT_FAILED: {type(error).__name__}: {error}") from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
