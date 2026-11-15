"""Build a metadata-only inventory of PSI investigation files via the public UI.

No file data is downloaded. The inventory records names, tree paths, sizes,
record IDs, and page text needed to plan a safe, bounded download batch.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import os

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(PROJECT_ROOT / "data" / "tmp" / "playwright-browsers"),
)
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REPORTS_DIR

PSI_ID_RE = re.compile(r"^PSI-\d+$", re.IGNORECASE)
PSI_HOST = "psi.nasa.gov"
FILE_EXTENSIONS = {
    ".csv", ".tsv", ".xlsx", ".xls", ".pdf", ".txt", ".json", ".jsonl",
    ".zip", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".mp4", ".mov",
    ".doc", ".docx", ".ppt", ".pptx", ".dat", ".h5", ".hdf5", ".nc",
    ".mat", ".avi", ".mpg", ".mpeg", ".m4v", ".xlsm", ".xml", ".html",
    ".md", ".log", ".rtf", ".tar", ".gz", ".7z", ".bin", ".raw",
}


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def find_value(mapping: dict, names: set[str]) -> Any:
    for key, value in mapping.items():
        if norm_key(str(key)) in names and value not in (None, ""):
            return value
    return None


def to_size(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        match = re.match(r"^(\d+(?:\.\d+)?)\s*(b|bytes?)?$", cleaned, re.IGNORECASE)
        if match:
            return int(float(match.group(1)))
    return None


def extract_name(node: dict) -> str | None:
    # NASA's /files/v2 tree uses displayName for both directories and files,
    # while key contains the object-storage path and often the authoritative
    # filename. Walk the known name fields in priority order.
    name_keys = (
        "filename", "originalfilename", "displayname", "name", "label", "title",
        "key", "path", "filepath", "contentdispositionfilename",
    )
    containers = (node, node.get("metadata", {}), node.get("file", {}))
    for wanted in name_keys:
        for container in containers:
            if not isinstance(container, dict):
                continue
            value = find_value(container, {norm_key(wanted)})
            if not isinstance(value, str):
                continue
            candidate = Path(value.replace("\\", "/").rstrip("/")).name
            suffix = Path(candidate).suffix.lower()
            if suffix in FILE_EXTENSIONS or (suffix and extract_size(node) is not None):
                return candidate
    return None


def extract_size(node: dict) -> int | None:
    size_keys = {"size", "filesize", "contentlength", "bytes", "length"}
    direct = to_size(find_value(node, size_keys))
    if direct is not None:
        return direct
    for key in ("metadata", "file", "attributes"):
        child = node.get(key)
        if isinstance(child, dict):
            value = to_size(find_value(child, size_keys))
            if value is not None:
                return value
    return None


def extract_id(node: dict) -> str | None:
    id_keys = {"id", "fileid", "recordid", "uuid", "oid"}
    value = find_value(node, id_keys)
    if isinstance(value, dict):
        value = value.get("$oid") or value.get("id")
    if value is None:
        nested = node.get("_id")
        if isinstance(nested, dict):
            value = nested.get("$oid")
        elif isinstance(nested, str):
            value = nested
    return str(value) if value is not None else None


def extract_storage_key(node: dict) -> str | None:
    value = find_value(node, {"key", "objectkey", "storagekey", "filepath", "path"})
    return value if isinstance(value, str) else None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"true", "yes", "1"}:
            return True
        if value.casefold() in {"false", "no", "0"}:
            return False
    return None


def flatten_inventory(payload: Any) -> tuple[list[dict], dict]:
    entries: list[dict] = []
    seen: set[tuple] = set()
    shape: dict[str, Any] = {}

    def inspect_shape(value: Any, depth: int = 0) -> Any:
        if depth >= 5:
            return type(value).__name__
        if isinstance(value, dict):
            return {str(key): inspect_shape(child, depth + 1) for key, child in list(value.items())[:30]}
        if isinstance(value, list):
            return {"list_length": len(value), "first_item": inspect_shape(value[0], depth + 1) if value else None}
        return type(value).__name__

    shape = inspect_shape(payload)

    def walk(
        value: Any,
        folders: list[str],
        inherited_restricted: bool = False,
        inherited_visible: bool | None = None,
    ) -> None:
        if isinstance(value, list):
            for child in value:
                walk(child, folders, inherited_restricted, inherited_visible)
            return
        if not isinstance(value, dict):
            return

        name = extract_name(value)
        next_folders = folders
        effective_restricted = (
            inherited_restricted
            or as_bool(value.get("restricted")) is True
            or as_bool(value.get("restrictedAccess")) is True
        )
        node_visible = as_bool(value.get("visible"))
        effective_visible = node_visible if node_visible is not None else inherited_visible
        if name:
            size = extract_size(value)
            record_id = extract_id(value)
            storage_key = extract_storage_key(value)
            object_path = storage_key.replace("\\", "/").strip("/") if storage_key else ""
            tree_path = object_path or "/".join([*folders, name])
            dedupe_key = (storage_key or record_id or tree_path, name)
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                is_restricted = value.get("restricted") is True or value.get("restrictedAccess") is True
                is_visible = value.get("visible") if isinstance(value.get("visible"), bool) else None
                entries.append({
                    "file_name": name,
                    "extension": Path(name).suffix.lower(),
                    "folder_path": str(Path(tree_path.replace("\\", "/")).parent).replace("\\", "/"),
                    "relative_tree_path": tree_path,
                    "size_bytes": size,
                    "record_id": record_id or storage_key,
                    "storage_key": storage_key,
                    "version": find_value(value, {"version", "versionid"}),
                    "etag": find_value(value, {"etag"}),
                    "checksum_algorithm": find_value(value, {"checksumalgorithm"}),
                    "mime_type": find_value(value, {"mimetype", "contenttype", "mediatype"}),
                    "visible": effective_visible,
                    "restricted": effective_restricted,
                    "download_eligible": effective_visible is True and not effective_restricted,
                    "status": (
                        "restricted_review_required" if effective_restricted
                        else "not_visible_review_required" if effective_visible is False
                        else "visibility_unknown_review_required" if effective_visible is None
                        else "discovered_size_known" if size is not None
                        else "discovered_size_unknown"
                    ),
                })
        else:
            folder_name = find_value(value, {"name", "displayname", "label", "title"})
            if isinstance(folder_name, str) and folder_name.strip():
                next_folders = [*folders, folder_name.strip()]

        for key, child in value.items():
            if isinstance(child, (dict, list)):
                walk(child, next_folders, effective_restricted, effective_visible)

    walk(payload, [])
    entries.sort(key=lambda row: (row["folder_path"].casefold(), row["file_name"].casefold()))
    return entries, shape


def load_psi_ids(all_sources: bool, one_id: str | None) -> list[str]:
    if one_id:
        normalized = one_id.upper()
        if not PSI_ID_RE.fullmatch(normalized):
            raise ValueError("Use an investigation ID such as PSI-10.")
        return [normalized]
    if not all_sources:
        return ["PSI-10"]
    links_path = PROJECT_ROOT / "config" / "source_links.json"
    links = json.loads(links_path.read_text(encoding="utf-8-sig"))
    ids = []
    for source in links.get("sources", []):
        if source.get("source_type") == "psi_investigation":
            value = source.get("investigation_id") or source.get("source_key", "")
            if PSI_ID_RE.fullmatch(value):
                ids.append(value.upper())
    return list(dict.fromkeys(ids))


async def inspect_one(context, investigation_id: str) -> dict:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    url = f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}"
    page = await context.new_page()
    payloads: list[Any] = []
    tasks: list[asyncio.Task] = []
    failures: list[str] = []

    async def read_json(response) -> None:
        try:
            payloads.append(await response.json())
        except Exception as error:
            failures.append(f"files_api_json_error:{type(error).__name__}")

    def response_event(response):
        parts = urlsplit(response.url)
        if parts.hostname == PSI_HOST and parts.path.endswith("/geode-py/ws/files/v2"):
            if response.status == 200 and "json" in response.headers.get("content-type", "").lower():
                tasks.append(asyncio.create_task(read_json(response)))
            else:
                failures.append(f"files_api_unexpected_response:{response.status}")

    page.on("response", response_event)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass
        button = page.get_by_role("button", name=re.compile(r"data\s+files\s+and\s+documents", re.IGNORECASE)).first
        if await button.count():
            try:
                await button.click(timeout=5_000)
            except Exception:
                pass
        if not payloads:
            try:
                await page.wait_for_timeout(2_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                pass
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        text = (await page.locator("body").inner_text(timeout=15_000))[:40_000]
        title = await page.title()
        if re.search(r"captcha|verify you are human|access denied|not authorized", text, re.IGNORECASE):
            failures.append("access_restriction_or_captcha_detected; no bypass attempted")
        if not payloads:
            return {
                "investigation_id": investigation_id,
                "investigation_url": url,
                "title": title,
                "page_text_characters": len(text),
                "page_text": text,
                "files_api_status": "not_captured",
                "files": [],
                "errors": failures or ["No /files/v2 JSON response was captured."],
            }
        payload = payloads[-1]
        files, shape = flatten_inventory(payload)
        known_sizes = [item["size_bytes"] for item in files if item["size_bytes"] is not None]
        return {
            "investigation_id": investigation_id,
            "investigation_url": url,
            "title": title,
            "page_text_characters": len(text),
            "page_text": text,
            "files_api_status": "captured",
            "api_payload_shape": shape,
            "file_count": len(files),
            "known_size_count": len(known_sizes),
            "unknown_size_count": len(files) - len(known_sizes),
            "total_known_size_bytes": sum(known_sizes),
            "files": files,
            "errors": failures,
        }
    except Exception as error:
        return {
            "investigation_id": investigation_id,
            "investigation_url": url,
            "files_api_status": "failed",
            "files": [],
            "errors": [f"{type(error).__name__}: {error}"],
        }
    finally:
        await page.close()


async def build_inventory(ids: list[str]) -> dict:
    from playwright.async_api import Error as PlaywrightError, async_playwright

    profile_path = PROJECT_ROOT / "data" / "tmp" / "psi_chromium_profile" / "inventory"
    profile_path.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=True,
            accept_downloads=False,
            service_workers="block",
        )
        investigations = []
        for index, investigation_id in enumerate(ids, start=1):
            print(f"Inventory {index}/{len(ids)}: {investigation_id}")
            investigations.append(await inspect_one(context, investigation_id))
            await asyncio.sleep(1)
        await context.close()

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inventory_only": True,
        "files_downloaded": False,
        "investigation_count": len(investigations),
        "investigations": investigations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory PSI files and sizes without downloading file data.")
    parser.add_argument("investigation_id", nargs="?", help="One ID, e.g. PSI-10. Defaults to PSI-10.")
    parser.add_argument("--all", action="store_true", help="Inventory every PSI source in config/source_links.json.")
    args = parser.parse_args()
    try:
        ids = load_psi_ids(args.all, args.investigation_id)
        result = asyncio.run(build_inventory(ids))
    except Exception as error:
        raise SystemExit(f"INVENTORY_FAILED: {error}") from error
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / ("psi_file_inventory_all.json" if args.all else f"psi_file_inventory_{ids[0]}.json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Inventory saved: {path}")
    print(f"Investigations: {len(result['investigations'])}")
    print("Files downloaded: no")
    for item in result["investigations"]:
        print(
            f"{item['investigation_id']}: API={item.get('files_api_status')} "
            f"files={item.get('file_count', 0)} known_size_bytes={item.get('total_known_size_bytes', 0)}"
        )


if __name__ == "__main__":
    main()
