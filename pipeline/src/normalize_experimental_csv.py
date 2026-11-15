"""Create structured, provenance-ready numeric observations from PSI CSV tables.

No units or meanings are inferred: units are read only from explicit header text.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from io import StringIO
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION, stable_id
from csv_encoding import read_csv_text

SKIP_NUMERIC_FIELDS = {"day", "test", "date", "gmt", "test date", "test gmt"}
NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
IDENTIFIER_SUFFIX = re.compile(r"\b(?:test|sample)\s*(?:#|number|no\.?)\s*$", re.IGNORECASE)


def parse_number(raw: str) -> int | float | None:
    value = raw.strip()
    if not value or not NUMBER_PATTERN.fullmatch(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() and not any(c in value.lower() for c in (".", "e")) else number


def unit_from_header(header: str) -> str | None:
    match = re.search(r"\(([^()]*)\)\s*$", header)
    if match:
        return match.group(1).strip() or None
    # Several PSI CSVs write units after a semicolon instead of parentheses.
    semicolon_unit = re.search(r";\s*([^;]+)\s*$", header)
    unit = semicolon_unit.group(1).strip() if semicolon_unit else ""
    return unit or None


def is_identifier_or_nonmeasurement_header(normalized_header: str) -> bool:
    """Avoid treating test/sample identifiers and date/time fields as quantities."""
    return (
        normalized_header in SKIP_NUMERIC_FIELDS
        or normalized_header.endswith(" identifier")
        or bool(IDENTIFIER_SUFFIX.search(normalized_header))
    )


def safe_column(header: str, index: int) -> str:
    return header.strip() if header.strip() else f"Unlabeled column {index + 1}"


def process_file(source_path: Path, investigation_id: str) -> tuple[Path, dict[str, Any]]:
    relative = source_path.relative_to(RAW_DATA_DIR).as_posix()
    output_path = PROCESSED_DATA_DIR / "structured" / f"{source_path.stem}_observations.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    dataset_id = stable_id("dataset", relative, file_hash)
    filename_lower = source_path.name.lower()
    if "experimental" in filename_lower:
        series_type, series_type_basis = "experiment", "filename_indicated"
    elif "model" in filename_lower:
        series_type, series_type_basis = "model", "filename_indicated"
    else:
        series_type, series_type_basis = "unknown", "needs_review"
    counts: Counter[str] = Counter()
    flagged_source_rows: list[int] = []
    observation_count = 0
    source_row_count = 0
    nonempty_row_count = 0

    csv_text, source_encoding = read_csv_text(source_path)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with StringIO(csv_text, newline="") as csv_file, temporary_path.open("w", encoding="utf-8", newline="\n") as output:
        reader = csv.reader(csv_file)
        raw_headers = next(reader, None)
        if not raw_headers:
            raise ValueError(f"CSV has no header row: {source_path.name}")
        headers = [safe_column(value, i) for i, value in enumerate(raw_headers)]
        normalized_headers = [re.sub(r"\s+", " ", h.strip().lower()) for h in headers]
        for source_row_number, values in enumerate(reader, start=2):
            source_row_count += 1
            if not any(value.strip() for value in values):
                counts["empty_rows_skipped"] += 1
                continue
            nonempty_row_count += 1
            if len(values) > len(headers) and any(v.strip() for v in values[len(headers):]):
                flagged_source_rows.append(source_row_number)
                counts["rows_with_unlabeled_extra_values"] += 1
            row_measurements = 0
            for column_index, raw_value in enumerate(values[:len(headers)]):
                if is_identifier_or_nonmeasurement_header(normalized_headers[column_index]):
                    continue
                number = parse_number(raw_value)
                if number is None:
                    continue
                header = headers[column_index]
                unit = unit_from_header(header)
                flags = []
                if source_row_number in flagged_source_rows:
                    flags.append("row_contains_unlabeled_extra_values")
                conditions = {
                    headers[i]: other_value.strip()
                    for i, other_value in enumerate(values[:len(headers)])
                    if i != column_index and other_value.strip()
                    and (is_identifier_or_nonmeasurement_header(normalized_headers[i]) or parse_number(other_value) is None)
                }
                if unit is None:
                    flags.append("unit_not_explicit_in_source_header")
                if series_type_basis == "needs_review":
                    flags.append("series_type_not_confirmed_from_filename")
                    counts["measurements_without_explicit_unit"] += 1
                record_id = stable_id("observation", dataset_id, source_row_number, column_index + 1, raw_value)
                source_row_values = {
                    headers[i]: value.strip()
                    for i, value in enumerate(values[:len(headers)])
                    if value.strip()
                }
                for extra_index, extra_value in enumerate(values[len(headers):], start=len(headers) + 1):
                    if extra_value.strip():
                        source_row_values[f"Unlabeled column {extra_index}"] = extra_value.strip()
                record = {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "numeric_observation",
                    "record_id": record_id,
                    "dataset_id": dataset_id,
                    "investigation_id": investigation_id,
                    "investigation_label": investigation_id,
                    "investigation_id_status": "verified",
                    "series_type": series_type,
                    "series_type_basis": series_type_basis,
                    "quantity_name": header,
                    "variable": header,
                    "value": number,
                    "value_raw": raw_value,
                    "unit": unit,
                    "unit_status": "provided" if unit else "needs_review",
                    "conditions": conditions,
                    "source_row_values": source_row_values,
                    "source_file": source_path.name,
                    "source_relative_path": relative,
                    "source_row_number": source_row_number,
                    "source_column_name": header,
                    "source_encoding": source_encoding,
                    "source_location": f"row:{source_row_number}",
                    "quality_flags": flags,
                    "record_status": "needs_review" if flags else "validated_structure",
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                counts[header] += 1
                observation_count += 1
                row_measurements += 1
            if row_measurements == 0:
                counts["nonempty_rows_without_numeric_observations"] += 1

    temporary_path.replace(output_path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "investigation_id": investigation_id,
        "source_file": source_path.name,
        "source_encoding": source_encoding,
        "source_relative_path": relative,
        "output": output_path.relative_to(PROJECT_ROOT).as_posix(),
        "source_row_count": source_row_count,
        "nonempty_source_rows": nonempty_row_count,
        "normalized_measurement_records": observation_count,
        "measurement_records_by_column": {key: value for key, value in counts.items()
                                           if key not in {"empty_rows_skipped", "rows_with_unlabeled_extra_values",
                                                          "measurements_without_explicit_unit",
                                                          "nonempty_rows_without_numeric_observations"}},
        "empty_rows_skipped": counts["empty_rows_skipped"],
        "rows_with_unlabeled_extra_values": flagged_source_rows,
        "measurements_without_explicit_unit": counts["measurements_without_explicit_unit"],
        "units_policy": "Only explicit units in column headers are assigned; all other units remain null and flagged.",
    }
    return output_path, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize numeric cells from CSV tables for one PSI investigation.")
    parser.add_argument("investigation_id", help="Investigation folder, e.g. PSI-159")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    investigation_dir = RAW_DATA_DIR / investigation_id
    if not investigation_dir.is_dir():
        raise SystemExit(f"Investigation raw folder not found: {investigation_dir}")
    csv_files = sorted(path for path in investigation_dir.rglob("*.csv") if path.is_file())
    if not csv_files:
        raise SystemExit(f"No CSV files found under {investigation_dir}")
    reports = [process_file(path, investigation_id)[1] for path in csv_files]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"normalization_{investigation_id}.json"
    report_path.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "investigation_id": investigation_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": reports,
        "summary": {"files": len(reports),
                    "normalized_measurement_records": sum(r["normalized_measurement_records"] for r in reports),
                    "measurements_without_explicit_unit": sum(r["measurements_without_explicit_unit"] for r in reports)},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "summary": {"files": len(reports),
        "normalized_measurement_records": sum(r["normalized_measurement_records"] for r in reports),
        "files_processed": [r["source_file"] for r in reports]}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
