"""Download a bounded, sequential pilot batch from an existing PSI inventory.

This runner never starts more than one browser download at a time. It defaults
to one file and requires explicit limits for larger runs. It does not delete
files or upload anything to a cloud service.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REPORTS_DIR
from download_psi_browser import paths_for, read_manifest, run_download


def load_inventory(investigation_id: str) -> dict:
    path = REPORTS_DIR / f"psi_file_inventory_{investigation_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Inventory is missing: {path}. Run inventory_psi_files.py {investigation_id} first."
        )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    matches = [row for row in report.get("investigations", []) if row.get("investigation_id", "").upper() == investigation_id]
    if not matches:
        raise ValueError(f"No {investigation_id} entry found in {path}.")
    return matches[0]


def prior_file_names(investigation_id: str) -> set[str]:
    manifest = paths_for(investigation_id)["manifest"]
    return {
        str(row.get("file_name", "")).casefold()
        for row in read_manifest(manifest)
        if row.get("investigation_id", "").upper() == investigation_id
        and row.get("download_status") in {"downloaded", "duplicate_content_detected"}
    }


async def download_batch(
    investigation_id: str,
    limit: int,
    max_total_bytes: int,
    extension: str | None,
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inventory = load_inventory(investigation_id)
    already = prior_file_names(investigation_id)
    candidates = []
    for record in inventory.get("files", []):
        if record.get("download_eligible") is not True:
            continue
        if record.get("file_name", "").casefold() in already:
            continue
        if extension and record.get("extension", "").casefold() != extension.casefold():
            continue
        candidates.append(record)
    candidates.sort(key=lambda row: (row.get("size_bytes") is None, row.get("size_bytes") or 0, row.get("file_name", "").casefold()))

    downloaded_bytes = 0
    results: list[dict] = []
    for record in candidates:
        if len(results) >= limit:
            break
        known_size = record.get("size_bytes")
        if known_size is not None and downloaded_bytes + int(known_size) > max_total_bytes:
            results.append({
                "file_name": record.get("file_name"),
                "status": "skipped_total_byte_budget",
                "known_size_bytes": known_size,
            })
            continue
        try:
            result = await run_download(investigation_id, record["file_name"], record)
            result["batch_status"] = result.get("download_status", "downloaded")
            if result.get("download_status") == "downloaded":
                downloaded_bytes += int(result.get("size_bytes", 0))
            results.append(result)
        except Exception as error:
            results.append({
                "file_name": record.get("file_name"),
                "source_record_id": record.get("record_id"),
                "source_tree_path": record.get("relative_tree_path"),
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
            })

    report = {
        "schema_version": "1.0",
        "investigation_id": investigation_id,
        "investigation_url": inventory.get("investigation_url"),
        "started_at_utc": started_at,
        "inventory_file_count": inventory.get("file_count"),
        "inventory_known_size_count": inventory.get("known_size_count"),
        "requested_file_limit": limit,
        "max_total_bytes": max_total_bytes,
        "downloaded_bytes": downloaded_bytes,
        "attempted_or_skipped_count": len(results),
        "results": results,
        "note": "Files are retained in data/tmp/psi_downloads. No files are deleted or uploaded.",
    }
    output = REPORTS_DIR / f"psi_download_batch_{investigation_id}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sequential, bounded NASA PSI downloader; defaults to a one-file pilot.")
    parser.add_argument("investigation_id", nargs="?", default="PSI-10")
    parser.add_argument("--limit", type=int, default=1, help="Maximum attempted files (default: 1).")
    parser.add_argument("--max-total-mib", type=int, default=100, help="Maximum successful download bytes (default: 100 MiB).")
    parser.add_argument("--extension", help="Optional extension filter, for example .txt or .csv.")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if args.limit < 1 or args.max_total_mib < 1:
        raise SystemExit("--limit and --max-total-mib must be positive.")
    if args.extension and not args.extension.startswith("."):
        args.extension = "." + args.extension
    report = asyncio.run(download_batch(investigation_id, args.limit, args.max_total_mib * 1024 * 1024, args.extension))
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    for result in report["results"]:
        print(json.dumps({key: result.get(key) for key in ("file_name", "status", "batch_status", "size_bytes", "error", "source_tree_path") if result.get(key) is not None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
