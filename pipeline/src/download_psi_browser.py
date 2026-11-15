"""Discover and download one public NASA PSI file through a private Playwright profile.

Uses Playwright-managed Chromium, never the user's installed Chrome profile.
Downloads are limited to one CSV file per invocation and remain in data/tmp.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Keep the managed browser binary in the project's ignored temporary area rather
# than the personal Chrome profile or a shared browser install directory.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(PROJECT_ROOT / "data" / "tmp" / "playwright-browsers"),
)
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REPORTS_DIR

PSI_ID_RE = re.compile(r"^PSI-\d+$", re.IGNORECASE)
NASA_HOST = "psi.nasa.gov"
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_DISCOVERY_SECONDS = 90
DOWNLOAD_RETRIES = 3


def paths_for(investigation_id: str) -> dict[str, Path]:
    base = PROJECT_ROOT / "data" / "tmp"
    return {
        "downloads": base / "psi_downloads" / investigation_id,
        "profile": base / "psi_chromium_profile" / investigation_id,
        "manifest": PROJECT_ROOT / "data" / "tmp" / "psi_download_manifest.jsonl",
        "report": REPORTS_DIR / f"psi_browser_download_{investigation_id}.json",
    }


def safe_filename(value: str) -> str:
    value = value.replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9._() -]+", "_", value).strip(" .")
    if not value or value in {".", ".."}:
        raise ValueError("The NASA page did not provide a safe file name.")
    return value[:180]


def observed_downloads(urls: list[str], investigation_id: str) -> list[tuple[str, str]]:
    expected_path = f"/geode-py/ws/studies/{investigation_id}/download"
    found: dict[str, str] = {}
    for url in urls:
        parts = urlsplit(url)
        if parts.hostname != NASA_HOST or parts.path != expected_path:
            continue
        query = parse_qs(parts.query)
        names = query.get("file", [])
        if not names:
            continue
        name = unquote(names[0])
        found.setdefault(name, url)
    return sorted(found.items(), key=lambda item: (Path(item[0]).suffix.lower() != ".csv", item[0].lower()))


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def validate_saved_file(path: Path) -> dict:
    """Validate the saved artifact itself; response headers can describe wrappers."""
    if path.suffix.lower() == ".csv":
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                if len(header) < 2 or any("<html" in cell.lower() for cell in header):
                    return {"format": "csv", "valid": False, "reason": "invalid_or_html_header"}
                row_count = 0
                bad_rows: list[int] = []
                for line_number, row in enumerate(reader, start=2):
                    if not row or not any(cell.strip() for cell in row):
                        continue
                    row_count += 1
                    if len(row) != len(header):
                        if len(bad_rows) < 20:
                            bad_rows.append(line_number)
                return {
                    "format": "csv",
                    "valid": row_count > 0 and not bad_rows,
                    "header_columns": len(header),
                    "data_rows": row_count,
                    "malformed_row_lines": bad_rows,
                    "reason": None if row_count > 0 and not bad_rows else "empty_or_inconsistent_csv",
                }
        except (UnicodeDecodeError, csv.Error, OSError) as error:
            return {"format": "csv", "valid": False, "reason": f"parse_error:{type(error).__name__}"}

    if path.suffix.lower() in {".txt", ".log", ".md", ".xml", ".json", ".jsonl", ".html"}:
        try:
            sample = path.read_bytes()[:64 * 1024]
            decoded = sample.decode("utf-8-sig")
            compact = decoded.lstrip().lower()
            html_error = compact.startswith(("<!doctype html", "<html")) or "access denied" in compact[:500]
            return {
                "format": path.suffix.lower().lstrip("."),
                "valid": bool(sample.strip()) and not html_error,
                "reason": "empty_or_html_response" if not sample.strip() or html_error else None,
            }
        except (UnicodeDecodeError, OSError) as error:
            return {"format": path.suffix.lower().lstrip("."), "valid": False, "reason": f"parse_error:{type(error).__name__}"}

    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            from zipfile import ZipFile, BadZipFile

            with ZipFile(path) as archive:
                valid = "[Content_Types].xml" in archive.namelist() and "xl/workbook.xml" in archive.namelist()
            return {"format": "xlsx", "valid": valid, "reason": None if valid else "invalid_workbook_structure"}
        except (BadZipFile, OSError) as error:
            return {"format": "xlsx", "valid": False, "reason": f"parse_error:{type(error).__name__}"}

    with path.open("rb") as handle:
        signature = handle.read(8)
    signatures = {
        ".pdf": (b"%PDF-", "pdf"),
        ".png": (b"\x89PNG\r\n\x1a\n", "png"),
        ".jpg": (b"\xff\xd8\xff", "jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "jpeg"),
        ".zip": (b"PK\x03\x04", "zip"),
    }
    expected = signatures.get(path.suffix.lower())
    if expected:
        valid = signature.startswith(expected[0])
        return {"format": expected[1], "valid": valid, "reason": None if valid else "signature_mismatch"}
    return {"format": "unknown", "valid": False, "reason": "no_validator_for_extension"}


async def visible_locator(locator):
    count = await locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


async def click_capture_download(page, locator, timeout_ms: int = 45_000):
    async with page.expect_download(timeout=timeout_ms) as download_info:
        await locator.click(timeout=15_000)
    return await download_info.value


async def click_category_folder(page, filename: str) -> str | None:
    if await visible_locator(page.get_by_text(filename, exact=True)) is not None:
        return None
    match = re.match(r"^PSI-\d+_(.+?)_", filename, re.IGNORECASE)
    if not match:
        return None
    category = match.group(1).strip()
    locator = page.get_by_text(category, exact=True)
    visible = []
    for index in range(await locator.count()):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible():
                visible.append(candidate)
        except Exception:
            continue
    # The last matching item is usually the folder entry in the Data Files tree;
    # earlier matches can be headings in the investigation's descriptive tables.
    if not visible:
        return None
    try:
        await visible[-1].click(timeout=5_000)
        await page.wait_for_timeout(1_500)
        return category
    except Exception as error:
        logging.info("Could not expand inferred folder %s: %s", category, error)
        return category


async def open_inventory_folder(page, tree_path: str | None) -> None:
    """Expand the catalog folders named by an inventory object path."""
    if not tree_path:
        return
    parts = [part for part in tree_path.replace("\\", "/").split("/") if part]
    # NASA object keys are normally psi-data/<investigation>/<folder>/.../<file>.
    folder_parts = parts[2:-1] if len(parts) >= 3 else parts[:-1]
    for folder in folder_parts:
        locator = page.get_by_text(folder, exact=True)
        visible = []
        for index in range(await locator.count()):
            candidate = locator.nth(index)
            try:
                if await candidate.is_visible():
                    visible.append(candidate)
            except Exception:
                continue
        if not visible:
            continue
        try:
            await visible[-1].click(timeout=5_000)
            await page.wait_for_timeout(500)
        except Exception as error:
            logging.info("Could not expand inventory folder %s: %s", folder, error)


async def search_file_tree(page, filename: str) -> None:
    """Use the catalog search field so paginated folders expose the target row."""
    inputs = page.locator("input")
    for index in range(await inputs.count()):
        field = inputs.nth(index)
        try:
            if not await field.is_visible() or not await field.is_enabled():
                continue
            hint = " ".join(filter(None, [await field.get_attribute("placeholder"), await field.get_attribute("aria-label"), await field.get_attribute("name")])).casefold()
            if "search" in hint and ("file" in hint or "document" in hint):
                await field.fill(filename, timeout=5_000)
                await page.wait_for_timeout(800)
                return
        except Exception:
            continue


async def select_file_checkbox(page, filename: str) -> bool:
    checkboxes = page.locator("input[type='checkbox'], [role='checkbox']")
    for index in range(await checkboxes.count()):
        checkbox = checkboxes.nth(index)
        try:
            if not await checkbox.is_visible() or not await checkbox.is_enabled():
                continue
            belongs_to_file = await checkbox.evaluate(
                """(el, target) => {
                    let node = el;
                    for (let depth = 0; node && depth < 8; depth++, node = node.parentElement) {
                        const text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                        if (text.includes(target)) return true;
                    }
                    return false;
                }""",
                filename,
            )
            if not belongs_to_file:
                continue
            if await checkbox.get_attribute("type") == "checkbox":
                await checkbox.check(timeout=5_000)
            elif await checkbox.get_attribute("aria-checked") != "true":
                await checkbox.click(timeout=5_000)
            return True
        except Exception as error:
            logging.info("Could not select file checkbox: %s", error)
    clicked = await page.evaluate("""(target) => {
        const norm = value => (value || '').replace(/\\s+/g, ' ').trim();
        const exact = [...document.querySelectorAll('body *')].filter(el => el.children.length === 0 && norm(el.textContent) === target);
        const selectors = 'input[type="checkbox"], [role="checkbox"], mat-checkbox, .mat-mdc-checkbox';
        for (const label of exact) {
            let node = label;
            for (let depth = 0; node && depth < 10; depth++, node = node.parentElement) {
                const checkbox = node.matches(selectors) ? node : node.querySelector(selectors);
                if (!checkbox) continue;
                if (checkbox.matches('input[type="checkbox"]') && !checkbox.checked) checkbox.click();
                else if (checkbox.getAttribute('aria-checked') !== 'true') checkbox.click();
                return true;
            }
        }
        return false;
    }""", filename)
    if clicked:
        await page.wait_for_timeout(500)
        return True
    return False


async def visible_download_controls(page) -> tuple[list[tuple[str, object]], list[dict]]:
    controls = page.locator("button, [role='button'], [mattooltip], [aria-label]")
    download_actions: list[tuple[str, object]] = []
    diagnostics: list[dict] = []
    seen: set[str] = set()
    for index in range(await controls.count()):
        control = controls.nth(index)
        try:
            if not await control.is_visible():
                continue
            text = " ".join((await control.inner_text(timeout=300)).split())
            aria = await control.get_attribute("aria-label") or ""
            title = await control.get_attribute("title") or ""
            tooltip = await control.get_attribute("mattooltip") or ""
            icon_text = await control.locator("mat-icon, .material-icons").all_inner_texts()
            icon_text = " ".join(" ".join(icon_text).split())[:100]
            label = " ".join(part for part in (text, aria, title, tooltip, icon_text) if part).strip()
            if not label:
                continue
            identity = label[:240]
            if identity in seen:
                continue
            seen.add(identity)
            enabled = await control.is_enabled()
            diagnostics.append({"label": identity, "enabled": enabled})
            if enabled and re.search(r"download|file_download|save_alt|get_app", label, re.IGNORECASE):
                if re.search(r"data files and documents", label, re.IGNORECASE):
                    continue
                download_actions.append((identity, control))
        except Exception:
            continue
    return download_actions, diagnostics


async def click_candidate_download(page, filename: str, click_file_row: bool, tree_path: str | None = None):
    if click_file_row:
        if tree_path:
            await open_inventory_folder(page, tree_path)
        else:
            inferred_category = await click_category_folder(page, filename)
            if inferred_category:
                logging.info("Opened likely file category folder: %s", inferred_category)
        await search_file_tree(page, filename)
        exact = await visible_locator(page.get_by_text(filename, exact=True))
        if exact is None:
            exact = await visible_locator(page.get_by_text(filename, exact=False))
        if exact is None:
            raise RuntimeError(
                "The file appeared in NASA's network routes but not as a visible file row. "
                "No control was clicked and no file was downloaded."
            )

        # Text-like assets open a NASA content/preview route on row click rather
        # than starting a download. Select those rows first, then use the toolbar.
        preview_extensions = {".txt", ".log", ".json", ".jsonl", ".md", ".xml"}
        if Path(filename).suffix.lower() not in preview_extensions:
            try:
                return await click_capture_download(page, exact)
            except Exception as first_error:
                logging.info("Clicking the file row did not start a download: %s", first_error)

        checkbox_selected = await select_file_checkbox(page, filename)
        if checkbox_selected:
            logging.info("Selected the checkbox belonging to %s", filename)

    # Other versions select a row first, then expose a JavaScript download action.
    labels, diagnostics = await visible_download_controls(page)

    for label, button in labels:
        logging.info("Trying visible download action: %s", label[:180])
        try:
            return await click_capture_download(page, button)
        except Exception as error:
            logging.info("Download action did not start a download: %s", error)
    raise RuntimeError(
        "The file row was found, but no visible JavaScript download action produced a browser download. "
        f"Visible controls after file selection: {diagnostics[:60]}. "
        "No CAPTCHA, login, or access restriction was bypassed."
    )


async def run_download(investigation_id: str, selected_name: str | None, inventory_entry: dict | None = None) -> dict:
    try:
        from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright's Python package is required. Install it only after reviewing requirements.txt."
        ) from error

    locations = paths_for(investigation_id)
    for key in ("downloads", "profile"):
        locations[key].mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=REPORTS_DIR / "psi_browser_download.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    investigation_url = f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}"
    requested_urls: list[str] = []
    response_facts: list[dict] = []

    async with async_playwright() as playwright:
        # The directory is created by this script, separate from all installed Chrome profiles.
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(locations["profile"]),
            headless=True,
            accept_downloads=True,
            downloads_path=str(locations["downloads"]),
            service_workers="block",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        page.on("request", lambda request: requested_urls.append(request.url))

        def on_response(response):
            try:
                parts = urlsplit(response.url)
                if parts.hostname == NASA_HOST and (
                    parts.path.endswith("/download") or parts.path.endswith("/files/v2")
                ):
                    response_facts.append({
                        "status": response.status,
                        "path": parts.path,
                        "content_type": response.headers.get("content-type", ""),
                        "content_length": response.headers.get("content-length"),
                    })
            except Exception:
                pass

        page.on("response", on_response)
        await page.goto(investigation_url, wait_until="domcontentloaded", timeout=90_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            logging.info("Network did not become idle during initial load; continuing with observed UI.")

        page_text = (await page.locator("body").inner_text(timeout=15_000)).lower()
        if re.search(r"captcha|verify you are human|access denied|not authorized", page_text):
            await context.close()
            raise RuntimeError(
                "NASA displayed an access restriction or CAPTCHA. The downloader stops and will not bypass it."
            )

        section = await visible_locator(
            page.get_by_role("button", name=re.compile(r"data\s+files\s+and\s+documents", re.IGNORECASE))
        )
        if section is None:
            section = await visible_locator(
                page.get_by_text(re.compile(r"data\s+files\s+and\s+documents", re.IGNORECASE))
            )
        if section is not None:
            try:
                await section.click(timeout=5_000)
            except Exception:
                logging.info("Data Files section was not clickable; checking current rendered state.")

        deadline = asyncio.get_running_loop().time() + MAX_DISCOVERY_SECONDS
        candidates: list[tuple[str, str]] = []
        while asyncio.get_running_loop().time() < deadline:
            candidates = observed_downloads(requested_urls, investigation_id)
            if candidates:
                break
            await page.wait_for_timeout(1_000)

        inventory_name = (inventory_entry or {}).get("file_name")
        inventory_path = (inventory_entry or {}).get("relative_tree_path")
        if not candidates and not (selected_name and inventory_path and inventory_name == selected_name):
            body = (await page.locator("body").inner_text(timeout=10_000))[:8_000]
            await context.close()
            raise RuntimeError(
                "No downloadable file route was observed after opening the data section. "
                f"Rendered page excerpt: {body}"
            )

        available_names = [name for name, _ in candidates]
        if selected_name:
            exact_names = [name for name in available_names if name.casefold() == selected_name.casefold()]
            if exact_names:
                filename = exact_names[0]
            elif inventory_path and inventory_name == selected_name:
                # Deeply nested files may not generate a route until their folder opens.
                filename = selected_name
            else:
                await context.close()
                raise RuntimeError(f"Requested file was not observed on the page: {selected_name}")
        else:
            csv_names = [name for name in available_names if Path(name).suffix.lower() == ".csv"]
            filename = csv_names[0] if csv_names else available_names[0]

        target = locations["downloads"] / safe_filename(filename)
        if target.exists():
            await context.close()
            raise FileExistsError(
                f"Refusing to overwrite existing path {target}; inspect or move it manually before retrying."
            )
        prior_manifest = read_manifest(locations["manifest"])
        source_url = next(
            (url for name, url in candidates if name == filename),
            f"https://{NASA_HOST}/geode-py/ws/studies/{investigation_id}/download?"
            + urlencode({"file": filename, "version": (inventory_entry or {}).get("version") or 1, "redirect": "false"}),
        )
        if any(
            row.get("investigation_url") == investigation_url and row.get("file_name") == filename
            for row in prior_manifest
        ):
            await context.close()
            raise RuntimeError(
                "Duplicate detected in the download manifest; no new download was started."
            )

        download = None
        last_error: Exception | None = None
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                logging.info("Download attempt %s/%s: %s %s", attempt, DOWNLOAD_RETRIES, investigation_id, filename)
                download = await click_candidate_download(
                    page, filename, click_file_row=(attempt == 1), tree_path=inventory_path
                )
                break
            except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as error:
                last_error = error
                logging.warning("Download attempt %s failed: %s", attempt, error)
                if attempt < DOWNLOAD_RETRIES:
                    await page.wait_for_timeout(1_000 * attempt)

        if download is None:
            body = (await page.locator("body").inner_text(timeout=10_000))[:8_000]
            await context.close()
            raise RuntimeError(f"One-file pilot failed after {DOWNLOAD_RETRIES} attempts: {last_error}. Page excerpt: {body}")

        suggested = safe_filename(download.suggested_filename or filename)
        if target.exists():
            await context.close()
            raise FileExistsError(f"Refusing to overwrite existing target: {target}")
        if suggested.casefold() != target.name.casefold():
            logging.info("Browser suggested filename %s; retaining portal filename %s", suggested, target.name)
        try:
            await download.save_as(str(target))
        except Exception:
            await context.close()
            raise
        failure = await download.failure()
        await context.close()

    if failure:
        raise RuntimeError(f"Browser reported download failure: {failure}. The partial file was retained at {target}.")
    size = target.stat().st_size
    if not size:
        raise RuntimeError(f"Browser created an empty file at {target}; it was retained for inspection.")
    if size > MAX_FILE_BYTES:
        raise RuntimeError(
            f"Pilot file is {size:,} bytes, above the 50 MiB limit. It was retained at {target}; no more files were downloaded."
        )
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    known_hashes = {row.get("sha256") for row in prior_manifest}
    duplicate_content = digest in known_hashes
    result = {
        "schema_version": "1.0",
        "investigation_id": investigation_id,
        "investigation_url": investigation_url,
        "source_download_url": source_url,
        "file_name": target.name,
        "source_record_id": (inventory_entry or {}).get("record_id"),
        "source_tree_path": (inventory_entry or {}).get("relative_tree_path"),
        "source_version": (inventory_entry or {}).get("version"),
        "temporary_path": str(target),
        "size_bytes": size,
        "sha256": digest,
        "download_status": "duplicate_content_detected" if duplicate_content else "downloaded",
        "http_status": next(
            (fact["status"] for fact in reversed(response_facts) if fact["path"].endswith("/download")),
            None,
        ),
        "content_type": next(
            (fact["content_type"] for fact in reversed(response_facts) if fact["path"].endswith("/download")),
            None,
        ),
        "response_facts": response_facts[-10:],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "personal_chrome_profile_used": False,
        "profile_path": str(locations["profile"]),
        "processing_status": "raw_pilot_needs_content_review",
    }
    result["content_validation"] = validate_saved_file(target)
    result["processing_status"] = (
        "raw_pilot_validated" if result["content_validation"]["valid"] else "raw_pilot_needs_review"
    )
    with locations["manifest"].open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    locations["report"].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logging.info("Pilot result: %s", json.dumps(result, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover PSI files and download at most one file via isolated Chromium.")
    parser.add_argument("investigation_id", nargs="?", default="PSI-10")
    parser.add_argument("--file", help="Optional exact filename to download from the page's observed file routes.")
    parser.add_argument("--tree-path", help="Optional inventory relative_tree_path for provenance in the download manifest.")
    parser.add_argument("--record-id", help="Optional NASA inventory record ID for provenance in the download manifest.")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if not PSI_ID_RE.fullmatch(investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-10.")
    try:
        metadata = {"relative_tree_path": args.tree_path, "record_id": args.record_id}
        result = asyncio.run(run_download(investigation_id, args.file, metadata))
    except Exception as error:
        raise SystemExit(f"PILOT_FAILED: {error}") from error
    print("At most one file was downloaded.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
