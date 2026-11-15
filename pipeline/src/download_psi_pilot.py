"""Download one small PSI file observed by the browser probe, with provenance.

This is deliberately a one-file pilot. It does not enumerate or bulk-download
an investigation. The probe must first record the NASA download endpoint.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, REPORTS_DIR

PSI_ID_RE = re.compile(r"^PSI-\d+$", re.IGNORECASE)
MAX_PILOT_BYTES = 50 * 1024 * 1024


def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name).strip(" .")
    if not name or name in {".", ".."}:
        raise ValueError("NASA endpoint did not provide a safe filename.")
    return name[:180]


def find_candidate(investigation_id: str) -> tuple[str, str]:
    report_path = REPORTS_DIR / f"psi_browser_probe_{investigation_id}.json"
    if not report_path.is_file():
        raise FileNotFoundError(
            f"Probe report not found: {report_path}. Run inspect_psi_browser.py first."
        )
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    prefix = f"https://psi.nasa.gov/geode-py/ws/studies/{investigation_id}/download"
    candidates: list[tuple[str, str]] = []
    for item in report.get("network_requests", []):
        url = item.get("url", "")
        if item.get("method") != "GET" or not url.startswith(prefix):
            continue
        query = parse_qs(urlsplit(url).query)
        file_values = query.get("file", [])
        if not file_values:
            continue
        filename = unquote(file_values[0].replace("+", " "))
        # Use a CSV as the first pilot when available: it is compact and can be
        # inspected as text. Other formats remain available for later batches.
        candidates.append((filename, url))
    candidates.sort(key=lambda item: (Path(item[0]).suffix.lower() != ".csv", item[0].lower()))
    if not candidates:
        raise RuntimeError(
            f"No observed NASA file-download endpoint for {investigation_id}. "
            "Re-run the browser probe and inspect its report."
        )
    return candidates[0]


async def download_one(url: str, investigation_id: str, filename: str) -> dict:
    try:
        from playwright.async_api import Error as PlaywrightError, async_playwright
    except ImportError as error:
        raise RuntimeError("Install project dependencies: python -m pip install -r requirements.txt") from error

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
        except PlaywrightError:
            browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=False)
        page = await context.new_page()
        await page.goto(
            f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}",
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightError:
            pass

        # Reuse the browser context so any public-site session cookies are sent.
        response = await context.request.get(url, timeout=90_000, max_redirects=10)
        status = response.status
        headers = response.headers
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        content_disposition = headers.get("content-disposition", "")
        body = await response.body()
        final_url = urlsplit(response.url)
        await context.close()
        await browser.close()

    if status < 200 or status >= 300:
        raise RuntimeError(f"NASA download endpoint returned HTTP {status}.")
    if not body:
        raise RuntimeError("NASA returned an empty response; no file was saved.")
    if len(body) > MAX_PILOT_BYTES:
        raise RuntimeError(
            f"Pilot response is {len(body):,} bytes, above the 50 MiB safety limit; no file was saved."
        )

    # A 200 response can be an API message or an HTML error page, so reject
    # those instead of accidentally treating them as scientific data.
    prefix = body[:2048].lstrip().lower()
    if "json" in content_type or prefix.startswith((b"<!doctype html", b"<html")):
        raise RuntimeError(
            "NASA returned a JSON/HTML response, not the file bytes. "
            f"No file was saved. Content type: {content_type or '(missing)'}; "
            f"response bytes: {len(body):,}."
        )
    if content_type not in {
        "text/csv", "text/plain", "application/octet-stream",
        "application/csv", "application/vnd.ms-excel",
    } and not content_disposition:
        raise RuntimeError(
            f"Unexpected response type {content_type or '(missing)'!r}; no file was saved."
        )

    output_dir = RAW_DATA_DIR / investigation_id
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / safe_filename(filename)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing raw file: {target}")
    temporary = target.with_name(target.name + ".partial")
    temporary.write_bytes(body)
    temporary.replace(target)
    digest = hashlib.sha256(body).hexdigest()

    # Record the stable NASA API URL only; never write a redirected signed URL.
    result = {
        "schema_version": "1.0",
        "investigation_id": investigation_id,
        "source_url": url,
        "final_host": final_url.hostname,
        "filename": target.name,
        "raw_path": str(target.relative_to(PROJECT_ROOT)),
        "http_status": status,
        "content_type": content_type,
        "content_disposition_present": bool(content_disposition),
        "bytes": len(body),
        "sha256": digest,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "processing_status": "raw_pilot_saved_needs_content_review",
    }
    manifest = output_dir / "download_manifest.jsonl"
    with manifest.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one observed PSI file as a bounded pilot.")
    parser.add_argument("investigation_id", nargs="?", default="PSI-10")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if not PSI_ID_RE.fullmatch(investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-10.")
    try:
        filename, url = find_candidate(investigation_id)
        result = asyncio.run(download_one(url, investigation_id, filename))
    except Exception as error:
        raise SystemExit(f"PILOT_NOT_SAVED: {error}") from error
    print("One PSI pilot file saved.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
