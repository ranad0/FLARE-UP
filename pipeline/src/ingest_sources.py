"""Fetch approved NASA sources, safely unpack ZIPs, and record provenance.

PSI investigation pages are catalogs, not direct file URLs. By default this
records the readable page text and discovers file links without downloading a
whole investigation. Direct links can be supplied explicitly in the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import tempfile
import zipfile
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, REPORTS_DIR
from handlers.zip_handler import handle_zip
from source_registry import load_registry, save_registry
from data_contract import SCHEMA_VERSION


MAX_DOWNLOAD_BYTES = 1_000_000_000
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
USER_AGENT = "FlareUpDataIngest/1.0 (scientific source acquisition)"
SOURCE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SUPPORTED_SUFFIXES = {".pdf", ".csv", ".xlsx", ".txt", ".json", ".jsonl", ".vtt", ".srt", ".zip"}
CATALOG_SUFFIXES = SUPPORTED_SUFFIXES | {
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".tif", ".tiff", ".png",
    ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".avi", ".m4v",
}
WEB_HOSTS = {"nasa.gov", "www.nasa.gov", "science.nasa.gov", "psi.nasa.gov"}


class PageContent(HTMLParser):
    """Extract visible text and links from static NASA pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[dict[str, str]] = []
        self._skip_depth = 0
        self._link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag.lower() == "a" and attrs_map.get("href"):
            self._link = {"url": str(attrs_map["href"]), "text": ""}
        if tag.lower() in {"p", "div", "section", "article", "h1", "h2", "h3", "li", "tr", "br"}:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() == "a" and self._link is not None:
            self._link["text"] = " ".join(self._link["text"].split())
            self.links.append(self._link)
            self._link = None
        if tag.lower() in {"p", "div", "section", "article", "h1", "h2", "h3", "li", "tr"}:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)
            if self._link is not None:
                self._link["text"] += " " + cleaned


def is_nasa_host(host: str | None) -> bool:
    host = (host or "").lower().rstrip(".")
    return host in WEB_HOSTS or host.endswith(".nasa.gov")


def fetch_web_page(url: str) -> tuple[str, str]:
    """Fetch a NASA HTML page with host checks before request and redirect."""
    validate_public_https_url(url)
    if not is_nasa_host(urlsplit(url).hostname):
        raise ValueError("Web pages are accepted only from official nasa.gov hosts.")
    opener = build_opener(SafeRedirectHandler())
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with opener.open(request, timeout=45) as response:
        final_url = response.geturl()
        validate_public_https_url(final_url)
        if not is_nasa_host(urlsplit(final_url).hostname):
            raise ValueError("NASA page redirected outside nasa.gov; refusing the redirect.")
        media_type = response.headers.get_content_type().lower()
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Expected a NASA HTML page, received {media_type}.")
        data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError("NASA page exceeds the 10 MB HTML limit.")
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace"), final_url


def clean_page(html: str) -> tuple[str, list[dict[str, str]]]:
    parser = PageContent()
    parser.feed(html)
    text = re.sub(r"[ \t]+", " ", "\n".join(parser.text))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, parser.links


def store_text_record(source: dict[str, Any], registry: dict[str, Any], text: str,
                      source_url: str, source_type: str, source_group: str,
                      canonical_id: str | None = None,
                      identity_confirmed: bool = False) -> str:
    key = safe_token(str(source.get("source_key", "")), "source_key")
    folder = RAW_DATA_DIR / source_group / key
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    target = folder / f"{key}__{digest[:12]}.txt"
    if not target.exists():
        target.write_text(text + "\n", encoding="utf-8")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "source_key": key,
        "source_type": source_type,
        "source_folder_label": source_group,
        "source_group": source_group,
        "canonical_investigation_id": canonical_id,
        "investigation_id_status": "verified" if canonical_id and identity_confirmed and source.get("investigation_id_evidence_url") else ("unverified" if canonical_id else "unknown"),
        "investigation_id_evidence_url": redact_url(source.get("investigation_id_evidence_url")) if identity_confirmed else None,
        "citation_url": redact_url(str(source.get("citation_url") or source_url)),
        "source_url": redact_url(source_url),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": digest,
        "media_type": "text/plain",
        "original_filename": None,
    }
    append_registry(registry, target, metadata)
    return target.relative_to(RAW_DATA_DIR).as_posix()


def process_web_source(source: dict[str, Any], registry: dict[str, Any], source_type: str) -> dict[str, Any]:
    key = safe_token(str(source.get("source_key", "")), "source_key")
    url = str(source.get("url", ""))
    html, final_url = fetch_web_page(url)
    text, links = clean_page(html)
    canonical_id = source.get("investigation_id")
    group = safe_token(str(source.get("source_group") or canonical_id or "nasa-references"), "source_group")
    has_investigation_id = bool(
        canonical_id
        and re.search(rf"(?<![A-Za-z0-9]){re.escape(canonical_id)}(?![A-Za-z0-9])", text, re.IGNORECASE)
    )
    if not text or (
        source_type == "psi_investigation"
        and (len(text) < 200 or not has_investigation_id)
    ):
        return {
            "source_key": key,
            "status": "requires_dynamic_browser_adapter",
            "source_url": redact_url(final_url),
            "page_text_characters": len(text),
            "discovered_file_links": 0,
            "investigation_id_status": "unverified",
            "note": "The PSI response did not contain enough readable investigation content or the expected investigation ID. No placeholder text file was added; a dynamic PSI page/file-browser adapter is required.",
        }

    file_links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in links:
        absolute = urljoin(final_url, link["url"])
        parsed = urlsplit(absolute)
        suffix = Path(unquote(parsed.path)).suffix.lower()
        if parsed.scheme == "https" and suffix in CATALOG_SUFFIXES and absolute not in seen:
            seen.add(absolute)
            file_links.append({
                "name": link["text"] or Path(parsed.path).name,
                "url": redact_url(absolute) or absolute,
                "suffix": suffix,
                "pipeline_supported": suffix in SUPPORTED_SUFFIXES,
            })

    identity_confirmed = bool(
        canonical_id
        and re.search(rf"(?<![A-Za-z0-9]){re.escape(canonical_id)}(?![A-Za-z0-9])", text, re.IGNORECASE)
        and not re.search(r"investigation you requested is not available|page not found|\b404\b", text, re.IGNORECASE)
    ) if source_type == "psi_investigation" else False
    raw_file = store_text_record(
        source, registry, text, final_url, source_type, group, canonical_id, identity_confirmed
    )
    status = "catalogued"
    if source_type == "psi_investigation" and not file_links:
        status = "metadata_only_file_links_not_exposed"
    return {
        "source_key": key,
        "status": status,
        "raw_file": raw_file,
        "source_url": redact_url(final_url),
        "discovered_file_links": len(file_links),
        "file_links": file_links,
        "page_text_characters": len(text),
        "investigation_id_status": "verified" if identity_confirmed else ("unverified" if canonical_id else "unknown"),
        "download_note": "Discovered links are catalogued only. Add chosen file URLs as source_type=file entries to download and process them; PSI folders may contain very large files.",
        "file_access_note": (
            "No direct file URLs were present in the fetched page HTML. PSI's file browser may require a dynamic-page/API adapter."
            if status == "metadata_only_file_links_not_exposed" else None
        ),
    }


def validate_public_https_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs without embedded credentials are supported.")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Invalid URL port.") from error
    if port not in (None, 443):
        raise ValueError("Only standard HTTPS port 443 is supported.")

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, port or 443, type=socket.SOCK_STREAM)}
    except OSError as error:
        raise ValueError(f"Could not resolve source host {parsed.hostname!r}: {error}") from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("The source URL must resolve only to public IP addresses.")


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_token(value: str, field: str) -> str:
    if not SOURCE_KEY_RE.fullmatch(value) or ".." in value:
        raise ValueError(f"{field} must use letters, numbers, dot, underscore, or hyphen; no path separators.")
    return value


def redact_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    # Query parameters may contain expiring or account-specific credentials.
    safe_query_keys = {"id", "v", "lang", "language", "file"}
    query = "&".join(
        f"{key}=[redacted]" if key.lower() not in safe_query_keys else f"{key}={value}"
        for item in parsed.query.split("&") if item
        for key, _, value in [item.partition("=")]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def filename_from_response(response, url: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    message = Message()
    message["content-disposition"] = disposition
    name = message.get_filename()
    if not name:
        name = Path(unquote(urlsplit(url).path)).name
    name = name.replace("\\", "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable() and char not in '<>:"|?*')
    name = name.strip(" .")
    return name or "downloaded_source"


def download_to_stage(url: str, expected_sha256: str | None, staging_dir: Path) -> tuple[Path, str, str, str]:
    validate_public_https_url(url)
    opener = build_opener(SafeRedirectHandler())
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    stage_path: Path | None = None
    try:
        with opener.open(request, timeout=45) as response:
            media_type = response.headers.get_content_type().lower()
            if media_type in {"text/html", "application/xhtml+xml"}:
                raise ValueError("URL returned a web page, not a direct file. Use its direct download URL.")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"Download exceeds {MAX_DOWNLOAD_BYTES} byte limit.")

            filename = filename_from_response(response, response.geturl())
            staging_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix="flare-source-", suffix=".part", dir=staging_dir, delete=False) as output:
                stage_path = Path(output.name)
                digest = hashlib.sha256()
                total = 0
                while block := response.read(DOWNLOAD_CHUNK_BYTES):
                    total += len(block)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ValueError(f"Download exceeds {MAX_DOWNLOAD_BYTES} byte limit.")
                    digest.update(block)
                    output.write(block)

        checksum = digest.hexdigest()
        if expected_sha256 and checksum.lower() != expected_sha256.lower():
            raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, received {checksum}.")
        return stage_path, filename, media_type, checksum
    except (HTTPError, URLError, OSError) as error:
        if stage_path and stage_path.exists():
            stage_path.unlink()
        raise RuntimeError(f"Download failed: {error}") from error
    except Exception:
        if stage_path and stage_path.exists():
            stage_path.unlink()
        raise


def identify_suffix(path: Path, media_type: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if zipfile.is_zipfile(path):
        return ".zip"
    with path.open("rb") as source:
        prefix = source.read(1024)
    if prefix.startswith(b"%PDF-"):
        return ".pdf"
    if suffix in SUPPORTED_SUFFIXES:
        return suffix
    media_map = {
        "application/pdf": ".pdf",
        "text/csv": ".csv",
        "application/zip": ".zip",
        "application/x-zip-compressed": ".zip",
        "text/vtt": ".vtt",
        "application/x-subrip": ".srt",
        "text/plain": ".txt",
        "application/json": ".json",
    }
    return media_map.get(media_type, suffix or ".bin")


def youtube_video_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    valid_host = host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}
    if parsed.scheme != "https" or not valid_host:
        raise ValueError("YouTube source URL must be an HTTPS YouTube video URL.")
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = next((value for key, value in (item.split("=", 1) if "=" in item else (item, "") for item in parsed.query.split("&")) if key == "v"), "")
        if not video_id and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        raise ValueError("Could not parse a YouTube video ID from the URL.")
    return f"https://www.youtube.com/watch?v={video_id}"


def append_registry(registry: dict[str, Any], raw_path: Path, metadata: dict[str, Any]) -> None:
    relative = raw_path.relative_to(RAW_DATA_DIR).as_posix()
    registry["sources"][relative] = metadata


def process_source(source: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    key = safe_token(str(source.get("source_key", "")), "source_key")
    source_type = source.get("source_type", "file")
    canonical_id = source.get("investigation_id")
    source_group = safe_token(str(source.get("source_group") or canonical_id or "unassigned"), "source_group")
    folder_label = source_group
    base_dir = RAW_DATA_DIR / folder_label / key
    common = {
        "schema_version": SCHEMA_VERSION,
        "source_key": key,
        "source_type": source_type,
        "source_folder_label": folder_label,
        "source_group": source_group,
        "canonical_investigation_id": canonical_id,
        "investigation_id_status": "verified" if canonical_id and source.get("investigation_id_evidence_url") else ("unverified" if canonical_id else "unknown"),
        "investigation_id_evidence_url": redact_url(source.get("investigation_id_evidence_url")),
        "citation_url": redact_url(source.get("citation_url")),
    }

    if source_type in {"psi_investigation", "webpage"}:
        return process_web_source(source, registry, source_type)

    if source_type == "youtube":
        video_url = youtube_video_url(str(source.get("url", "")))
        transcript_url = source.get("transcript_url")
        if not transcript_url:
            return {
                "source_key": key,
                "status": "awaiting_transcript_source",
                "video_url": video_url,
                "note": "Add a direct VTT/SRT transcript_url or use authorized caption access; the video itself is not downloaded.",
            }
        stage, name, media_type, checksum = download_to_stage(
            str(transcript_url), source.get("expected_sha256"), PROJECT_ROOT / "work" / "source_staging"
        )
        suffix = identify_suffix(stage, media_type, name)
        if suffix not in {".vtt", ".srt"}:
            stage.unlink(missing_ok=True)
            raise ValueError("YouTube transcript_url must return a .vtt or .srt caption file.")
        base_dir = base_dir / "captions"
        base_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{key}__{checksum[:12]}{suffix}"
        target = base_dir / target_name
        if target.exists():
            stage.unlink(missing_ok=True)
        else:
            stage.replace(target)
        metadata = {
            **common,
            "video_url": video_url,
            "caption_source_url": redact_url(str(transcript_url)),
            "caption_language": source.get("language"),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": checksum,
            "media_type": media_type,
        }
        append_registry(registry, target, metadata)
        return {"source_key": key, "status": "downloaded_caption", "video_url": video_url, "raw_file": target.relative_to(RAW_DATA_DIR).as_posix(), "sha256": checksum}

    if source_type != "file":
        raise ValueError(f"Unsupported source_type: {source_type!r}")
    url = str(source.get("url", ""))
    stage, name, media_type, checksum = download_to_stage(
        url, source.get("expected_sha256"), PROJECT_ROOT / "work" / "source_staging"
    )
    suffix = identify_suffix(stage, media_type, name)
    if suffix not in SUPPORTED_SUFFIXES:
        stage.unlink(missing_ok=True)
        raise ValueError(f"Unsupported downloaded file type {suffix!r}. Supported: {sorted(SUPPORTED_SUFFIXES)}")
    target_name = f"{key}__{checksum[:12]}{suffix}"
    if suffix == ".zip":
        archive_dir = RAW_DATA_DIR / folder_label / "_archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / target_name
        if archive_path.exists():
            stage.unlink(missing_ok=True)
        else:
            stage.replace(archive_path)
        archive_origin = {
            **common,
            "source_url": redact_url(url),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": checksum,
            "media_type": media_type,
            "archive_member": None,
        }
        append_registry(registry, archive_path, archive_origin)
        extraction_dir = base_dir / "extracted"
        if extraction_dir.exists():
            extracted_paths = sorted(path for path in extraction_dir.rglob("*") if path.is_file())
        else:
            extracted_paths = handle_zip(archive_path, extraction_dir)
        for extracted_path in extracted_paths:
            member = extracted_path.relative_to(extraction_dir).as_posix()
            append_registry(
                registry,
                extracted_path,
                {**archive_origin, "archive_member": member, "sha256": file_sha256(extracted_path)},
            )
        return {
            "source_key": key,
            "status": "downloaded_and_extracted",
            "archive": archive_path.relative_to(RAW_DATA_DIR).as_posix(),
            "extracted_files": [path.relative_to(RAW_DATA_DIR).as_posix() for path in extracted_paths],
            "sha256": checksum,
        }

    base_dir.mkdir(parents=True, exist_ok=True)
    target = base_dir / target_name
    if target.exists():
        stage.unlink(missing_ok=True)
    else:
        stage.replace(target)
    metadata = {
        **common,
        "source_url": redact_url(url),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": checksum,
        "media_type": media_type,
        "original_filename": name,
    }
    append_registry(registry, target, metadata)
    return {"source_key": key, "status": "downloaded", "raw_file": target.relative_to(RAW_DATA_DIR).as_posix(), "sha256": checksum}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NASA files, web pages, PSI catalogs, and YouTube captions.")
    parser.add_argument("--manifest", default=str(PROJECT_ROOT / "config" / "source_links.json"))
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Source manifest not found: {manifest_path}. Copy config/source_links.example.json to config/source_links.json and add sources."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Manifest must contain a 'sources' array.")

    registry = load_registry()
    results = []
    for source in sources:
        try:
            result = process_source(source, registry)
        except Exception as error:
            result = {"source_key": source.get("source_key"), "status": "failed", "error": str(error)}
        results.append(result)
        print(f"{result['status'].upper()}: {result.get('source_key')}")

    save_registry(registry)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": manifest_path.relative_to(PROJECT_ROOT).as_posix() if manifest_path.is_relative_to(PROJECT_ROOT) else manifest_path.name,
        "summary": {
            "sources": len(results),
            "downloaded": sum(result["status"] in {"downloaded", "downloaded_caption", "downloaded_and_extracted"} for result in results),
            "catalogued_pages": sum(result["status"] == "catalogued" for result in results),
            "metadata_only_file_links_not_exposed": sum(result["status"] == "metadata_only_file_links_not_exposed" for result in results),
            "requires_dynamic_browser_adapter": sum(result["status"] == "requires_dynamic_browser_adapter" for result in results),
            "awaiting_transcript_source": sum(result["status"] == "awaiting_transcript_source" for result in results),
            "failed": sum(result["status"] == "failed" for result in results),
        },
        "sources": results,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "source_ingestion_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Ingestion report: {report_path}")
    print("Source registry saved.")


if __name__ == "__main__":
    main()
