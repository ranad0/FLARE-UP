"""Finalize JSONL outputs to a versioned RAG data contract and emit QA/manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION, PIPELINE_VERSION, apply_contract, stable_id
from source_registry import load_registry


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def find_source(record: dict[str, Any], output_path: Path) -> Path | None:
    rel = record.get("source_relative_path")
    if rel:
        candidate = RAW_DATA_DIR / Path(str(rel).replace("/", "\\"))
        if candidate.is_file():
            return candidate
    name = record.get("source_file")
    if name:
        matches = list(RAW_DATA_DIR.rglob(str(name)))
        if len(matches) == 1:
            return matches[0]
    relative_output = output_path.relative_to(PROCESSED_DATA_DIR)
    stem = relative_output.with_suffix("").name
    parent = RAW_DATA_DIR / relative_output.parent
    for ext in (".pdf", ".xlsx", ".csv", ".txt", ".json", ".jsonl", ".vtt", ".srt"):
        candidate = parent / (stem + ext)
        if candidate.is_file():
            return candidate
    return None


def location_id_fields(record: dict[str, Any]) -> None:
    location = str(record.get("source_location") or "")
    page = record.get("page_number")
    if page is None:
        match = re.search(r"page:(\d+)", location)
        page = int(match.group(1)) if match else None
    if page is not None:
        record["page_number"] = page
        record["page_id"] = stable_id("page", record["document_id"], page)
    sheet = record.get("sheet_name")
    if sheet:
        record["table_id"] = stable_id("table", record["document_id"], sheet)
    row = record.get("row_number", record.get("source_row_number"))
    if row is not None and not sheet:
        record.setdefault("table_id", stable_id("table", record["document_id"], "csv"))
    if row is not None:
        record["row_id"] = stable_id("row", record["document_id"], sheet or "csv", row)
        if not location:
            record["source_location"] = f"sheet:{sheet}:row:{row}" if sheet else f"row:{row}"
    if record.get("record_type") == "visual_annotation":
        record.setdefault("caption", None)
        record.setdefault("caption_status", "needs_review")
        record.setdefault("figure_context", record.get("page_context"))
        record.setdefault("visual_interpretation_status", record.get("review_status", "needs_review"))
    provenance = record.setdefault("provenance", {})
    for key in ("page_id", "table_id", "row_id", "source_location"):
        if record.get(key) is not None:
            provenance[key] = record[key]


def expand_sample(record: dict[str, Any]) -> list[dict[str, Any]]:
    measurements = record.get("measurements")
    if record.get("record_type") != "time_series_sample" or not isinstance(measurements, list):
        return [record]
    expanded = []
    for measurement in measurements:
        if not isinstance(measurement, dict):
            continue
        item = {k: v for k, v in record.items() if k != "measurements"}
        item.update({
            "record_type": "time_series_observation",
            "quantity_name": measurement.get("name"),
            "value": measurement.get("value"),
            "value_raw": measurement.get("raw_value"),
            "unit": measurement.get("unit"),
            "source_column_name": measurement.get("source_column"),
        })
        item.pop("record_id", None)
        expanded.append(item)
    return expanded


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize processed JSONL records and emit QA/manifest.")
    parser.add_argument("--investigation", help="Finalize only one investigation batch, e.g. PSI-159.")
    parser.add_argument("--source-prefix", help="Finalize only a processed folder, e.g. nasa-combustion-reference/bass.")
    args = parser.parse_args()
    if args.investigation and args.source_prefix:
        raise SystemExit("Choose either --investigation or --source-prefix.")
    investigation_id = args.investigation.upper() if args.investigation else None
    if investigation_id and not re.fullmatch(r"PSI-\d+", investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-159.")
    if not PROCESSED_DATA_DIR.exists():
        raise FileNotFoundError(f"Processed folder missing: {PROCESSED_DATA_DIR}")
    prefix_parts = tuple(Path(args.source_prefix.replace("\\", "/")).parts) if args.source_prefix else ()
    if prefix_parts and (prefix_parts[0] != "nasa-combustion-reference"
                         or any(part in {".", ".."} for part in prefix_parts)):
        raise SystemExit("--source-prefix must stay under nasa-combustion-reference.")
    def matches_scope(path: Path) -> bool:
        parts = path.relative_to(PROCESSED_DATA_DIR).parts
        if investigation_id:
            return bool(parts) and (parts[0] == investigation_id
                or (path.parent.name == "structured" and path.name.startswith(f"{investigation_id}_")))
        if prefix_parts:
            return parts[:len(prefix_parts)] == prefix_parts
        return True

    jsonl_files = sorted(
        p for p in PROCESSED_DATA_DIR.rglob("*.jsonl")
        if p.is_file() and matches_scope(p)
    )
    source_hash_cache: dict[str, str] = {}
    registry_sources = load_registry().get("sources", {})
    errors: list[dict[str, str]] = []
    warnings: Counter[str] = Counter()
    file_entries = []

    for path in jsonl_files:
        if path.name.endswith(".tmp.jsonl"):
            continue
        rows: list[dict[str, Any]] = []
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Expected an object at line {line_no}")
                source = find_source(value, path)
                rel = source.relative_to(RAW_DATA_DIR).as_posix() if source else str(value.get("source_relative_path") or path.relative_to(PROCESSED_DATA_DIR).as_posix())
                source_file = source.name if source else str(value.get("source_file") or Path(rel).name)
                digest = None
                if source:
                    digest = source_hash_cache.setdefault(rel, sha256(source))
                origin = registry_sources.get(rel) if source else None
                candidates = expand_sample(value)
                for item in candidates:
                    item = apply_contract(item, rel, source_file, digest, origin)
                    location_id_fields(item)
                    if item.get("chunk_id") and item.get("investigation_id_status") == "unverified":
                        item["embedding_text"] = re.sub(r"^Investigation ID:.*$", f"Investigation label (unverified): {item.get('investigation_label')}", str(item.get("embedding_text") or ""), count=1, flags=re.MULTILINE)
                    if item.get("record_type") == "time_series_observation":
                        item["record_id"] = stable_id("obs", item["document_id"], item.get("source_row_number"), item.get("series_id"), item.get("quantity_name"))
                    # refresh provenance after parent IDs and measurement IDs are attached
                    provenance = item.get("provenance", {})
                    for key in ("page_id", "table_id", "row_id", "chunk_id", "record_id", "asset_id", "source_location"):
                        if item.get(key) is not None:
                            provenance[key] = item[key]
                    item["provenance"] = provenance
                    if item.get("investigation_id_status") == "unverified":
                        warnings["records_with_unverified_investigation_label"] += 1
                    if item.get("unit_status") == "needs_review":
                        warnings["records_with_unit_needing_review"] += 1
                    rows.append(item)
        except Exception as error:
            errors.append({"file": path.relative_to(PROCESSED_DATA_DIR).as_posix(), "error": str(error)})
            continue

        # Add a file-level table record for CSVs so rows have a table parent.
        first_csv_row = next((r for r in rows if r.get("record_type") in {"table_row", "row"} and r.get("columns")), None)
        if first_csv_row:
            source_rel = first_csv_row["source_relative_path"]
            source = RAW_DATA_DIR / Path(source_rel.replace("/", "\\"))
            digest = source_hash_cache.get(source_rel)
            origin = registry_sources.get(source_rel)
            table_record = apply_contract({
                "record_type": "table", "table_name": source.stem,
                "columns": first_csv_row["columns"], "table_id": stable_id("table", first_csv_row["document_id"], "csv")
            }, source_rel, source.name, digest, origin)
            table_exists = any(r.get("record_type") == "table" and r.get("source_relative_path") == source_rel for r in rows)
            if not table_exists:
                rows.insert(0, table_record)

        # Turn extracted PDF images into explicit figure-asset records.
        existing_assets = {(r.get("source_location"), r.get("image_reference")) for r in rows if r.get("record_type") == "figure_asset"}
        for page_record in list(rows):
            if page_record.get("record_type") != "page":
                continue
            source_rel = page_record["source_relative_path"]
            source = RAW_DATA_DIR / Path(source_rel.replace("/", "\\"))
            digest = source_hash_cache.get(source_rel)
            origin = registry_sources.get(source_rel)
            for image_ref in page_record.get("image_references") or []:
                key = (page_record.get("source_location"), image_ref)
                if key in existing_assets:
                    continue
                asset = apply_contract({
                    "record_type": "figure_asset", "page_number": page_record.get("page_number"),
                    "source_location": page_record.get("source_location"), "image_reference": image_ref,
                    "figure_context": page_record.get("text") or None, "caption": None,
                    "caption_status": "needs_review", "asset_status": "extracted_not_interpreted",
                    "visual_interpretation_status": "not_interpreted",
                }, source_rel, source.name, digest, origin)
                location_id_fields(asset)
                rows.append(asset)
                existing_assets.add(key)

        for row in rows:
            if row.get("record_type") == "time_series_observation" and isinstance(row.get("time"), dict):
                row["time_unit_status"] = "needs_review" if row["time"].get("unit") is None else "provided"
                if row["time_unit_status"] == "needs_review":
                    warnings["time_units_needing_review"] += 1
            if row.get("record_type") in {"figure_asset", "visual_annotation"}:
                row.setdefault("caption", None)
                row.setdefault("caption_status", "needs_review")
                row.setdefault("figure_context", row.get("page_context"))
                if row.get("caption_status") == "needs_review":
                    warnings["figure_captions_needing_review"] += 1

        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        temp.replace(path)
        file_entries.append({
            "path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
            "record_count": len(rows), "record_types": dict(Counter(str(r.get("record_type")) for r in rows)),
            "schema_version": SCHEMA_VERSION,
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []
    for path in jsonl_files:
        if path.exists():
            try:
                all_records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
            except Exception:
                pass
    if jsonl_files and not all_records:
        errors.append({
            "file": f"investigation:{investigation_id or 'all'}",
            "error": "No records were generated for the selected batch.",
        })
    required = ("schema_version", "record_type", "investigation_id", "investigation_label",
                "investigation_id_status", "document_id", "source_file", "source_relative_path",
                "source_sha256", "citation_url", "doi", "provenance")
    missing_fields = []
    for path in jsonl_files:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for field in required:
                if field not in record:
                    missing_fields.append({"file": path.name, "line": i, "field": field})
            if record.get("schema_version") != SCHEMA_VERSION:
                missing_fields.append({"file": path.name, "line": i, "field": "schema_version_mismatch"})
            if record.get("chunk_id") is not None:
                for field in ("chunk_id", "content_type", "source_location", "text", "embedding_text"):
                    if not record.get(field):
                        missing_fields.append({"file": path.name, "line": i, "field": field})
            if record.get("record_type") in {"numeric_observation", "time_series_observation"}:
                for field in ("record_id", "quantity_name", "value", "unit_status", "source_location"):
                    if field not in record or (record.get(field) is None and field != "value"):
                        missing_fields.append({"file": path.name, "line": i, "field": field})
                if "value" not in record or record.get("value") is None:
                    missing_fields.append({"file": path.name, "line": i, "field": "value"})
            if record.get("record_type") in {"figure_asset", "visual_annotation"}:
                for field in ("asset_id", "image_reference", "document_id", "source_location", "caption_status"):
                    if not record.get(field):
                        missing_fields.append({"file": path.name, "line": i, "field": field})
                asset_file = PROCESSED_DATA_DIR / str(record.get("image_reference") or "")
                if not asset_file.is_file():
                    missing_fields.append({"file": path.name, "line": i, "field": "image_reference_file_missing"})
    for asset_path in sorted(PROCESSED_DATA_DIR.rglob("*")):
        if (asset_path.is_file() and asset_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
                and matches_scope(asset_path)):
            file_entries.append({
                "path": asset_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(asset_path),
                "bytes": asset_path.stat().st_size,
                "asset_type": "image",
                "schema_version": SCHEMA_VERSION,
            })
    qa = {
        "schema_version": SCHEMA_VERSION, "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "structurally_valid_with_review_flags" if not errors and not missing_fields else "invalid",
        "summary": {"jsonl_files": sum("record_count" in entry for entry in file_entries), "records": len(all_records),
                    "errors": len(errors), "missing_required_fields": len(missing_fields),
                    "review_flags": dict(warnings)},
        "errors": errors, "missing_required_fields": missing_fields,
        "note": "Review flags preserve scientific uncertainty; they do not indicate structural failure.",
    }
    scope_name = investigation_id or (args.source_prefix.replace("/", "_").replace("\\", "_") if args.source_prefix else None)
    qa_report_path = REPORTS_DIR / (f"qa_report_{scope_name}.json" if scope_name else "qa_report.json")
    qa_report_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION, "pipeline_version": PIPELINE_VERSION,
        "batch_id": stable_id("batch", datetime.now(timezone.utc).isoformat(), *(entry["sha256"] for entry in file_entries)),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": qa["status"], "investigation_filter": investigation_id,
        "source_prefix_filter": args.source_prefix, "files": file_entries,
        "qa_report": qa_report_path.relative_to(ROOT).as_posix(),
    }
    manifest_path = REPORTS_DIR / (f"batch_manifest_{scope_name}.json" if scope_name else "batch_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Batch schema: {SCHEMA_VERSION}")
    print(f"JSONL files: {qa['summary']['jsonl_files']}; records: {len(all_records)}")
    print(f"QA status: {qa['status']}")
    print(f"Manifest: {manifest_path}")
    print(f"QA report: {qa_report_path}")


if __name__ == "__main__":
    main()
