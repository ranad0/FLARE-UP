"""Safely process one manually collected NASA PSI investigation.

Example: python src/process_manual_investigation.py PSI-159
Original archives are retained; duplicate ZIPs are inventoried but extracted once.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION
from handlers.csv_handler import handle_csv
from handlers.excel_handler import handle_excel
from handlers.ooxml_handler import handle_docx, handle_pptx
from handlers.pdf_handler import handle_pdf
from handlers.text_handler import handle_text
from handlers.zip_handler import handle_zip
from inventory import build_manifest
from source_registry import load_registry, save_registry, enrich_jsonl


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def base_origin(investigation_id: str, source_url: str, path: Path, digest: str) -> dict:
    origin = {
        "schema_version": SCHEMA_VERSION,
        "source_key": investigation_id,
        "source_type": "manual_psi_investigation_file",
        "source_group": investigation_id,
        "source_folder_label": investigation_id,
        "canonical_investigation_id": investigation_id,
        "investigation_id_status": "verified",
        "investigation_id_evidence_url": source_url,
        "source_url": source_url,
        "citation_url": source_url,
        "original_filename": path.name,
        "sha256": digest,
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if investigation_id == "PSI-25":
        origin["doi"] = "10.60555/4qc4-de67"
    return origin


def main() -> None:
    parser = argparse.ArgumentParser(description="Process manually collected files for one NASA PSI investigation.")
    parser.add_argument("investigation_id", help="Investigation folder, e.g. PSI-159")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if not re.fullmatch(r"PSI-\d+", investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-159.")

    investigation_dir = RAW_DATA_DIR / investigation_id
    if not investigation_dir.is_dir():
        raise FileNotFoundError(f"Raw investigation folder not found: {investigation_dir}")
    source_url = f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}"
    registry = load_registry()
    origins = registry.setdefault("sources", {})

    raw_files = sorted(path for path in investigation_dir.rglob("*") if path.is_file())
    original_archives = [path for path in raw_files if path.suffix.lower() == ".zip"
                         and "_archive_contents" not in path.parts]
    archive_hashes: dict[str, str] = {}
    archive_results = []
    extracted_sources: list[tuple[Path, Path, str]] = []

    # Register manually collected originals without changing them.
    for path in raw_files:
        relative = path.relative_to(RAW_DATA_DIR).as_posix()
        digest = sha256(path)
        origin = base_origin(investigation_id, source_url, path, digest)
        if path.suffix.lower() == ".zip":
            origin["archive_sha256"] = digest
        origins[relative] = origin

    for archive in original_archives:
        digest = sha256(archive)
        relative_archive = archive.relative_to(RAW_DATA_DIR).as_posix()
        if digest in archive_hashes:
            archive_results.append({
                "archive": relative_archive,
                "status": "duplicate_not_extracted",
                "duplicate_of": archive_hashes[digest],
                "sha256": digest,
            })
            continue
        archive_hashes[digest] = relative_archive
        destination = investigation_dir / "_archive_contents" / digest[:16]
        if not destination.exists():
            extracted = handle_zip(archive, destination)
        else:
            extracted = [path for path in destination.rglob("*") if path.is_file()]
            if not extracted:
                raise ValueError(f"Existing ZIP extraction folder is empty; inspect manually: {destination}")
        for member in extracted:
            relative_member = member.relative_to(RAW_DATA_DIR).as_posix()
            member_rel_to_archive_root = member.relative_to(destination).as_posix()
            member_origin = base_origin(investigation_id, source_url, member, sha256(member))
            member_origin.update({
                "source_type": "manual_psi_archive_member",
                "container_archive_path": relative_archive,
                "container_archive_sha256": digest,
                "container_member_path": member_rel_to_archive_root,
            })
            origins[relative_member] = member_origin
            extracted_sources.append((member, archive, digest))
        archive_results.append({
            "archive": relative_archive,
            "status": "extracted_once",
            "sha256": digest,
            "member_count": len(extracted),
            "members": [member.relative_to(destination).as_posix() for member in extracted],
        })

    save_registry(registry)

    process_files = sorted(
        path for path in investigation_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".txt", ".pdf", ".xlsx", ".docx", ".pptx"}
    )
    results = []
    for source_path in process_files:
        relative_source = source_path.relative_to(RAW_DATA_DIR).as_posix()
        extension = source_path.suffix.lower()
        if extension == ".csv":
            output_path, count = handle_csv(source_path)
            details = {"rows": count}
        elif extension == ".xlsx":
            output_path, count = handle_excel(source_path)
            details = {"worksheet_rows": count}
        elif extension == ".pdf":
            output_path, page_count, image_count = handle_pdf(source_path)
            count = page_count
            details = {"pages": page_count, "images_extracted": image_count}
        elif extension == ".docx":
            output_path, count, details = handle_docx(source_path)
        elif extension == ".pptx":
            output_path, count, details = handle_pptx(source_path)
        else:
            output_path, count = handle_text(source_path)
            details = {"lines": count}
        enrich_jsonl(output_path, origins.get(relative_source))
        results.append({
            "source_relative_path": relative_source,
            "output_relative_path": output_path.relative_to(PROJECT_ROOT).as_posix(),
            "status": "processed",
            "rows_or_lines": count,
            "details": details,
            "sha256": sha256(source_path),
        })

    manifest_path = build_manifest()
    report = {
        "schema_version": SCHEMA_VERSION,
        "investigation_id": investigation_id,
        "investigation_id_status": "verified",
        "source_url": source_url,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "archives": archive_results,
        "processed_files": results,
        "raw_inventory_manifest": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
        "note": "CSV rows preserve source columns and values. PDFs preserve page numbers and extracted image references. ZIP members are extracted only after path and size safety checks.",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"manual_ingestion_{investigation_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
