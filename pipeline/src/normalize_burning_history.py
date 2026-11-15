"""Normalize the PSI-117 MST_2024_Burning_history side-by-side CSV.

Each independent source block is processed separately. Row position across
blocks is never treated as evidence that samples belong to the same timepoint.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION


INVESTIGATION_ID = "PSI-117"
DATASET_ID = "MST_2024_Burning_history_Flame_diameter"
SOURCE_NAME = "PSI-117_Analyzed Data_MST_2024_Burning_history_Flame_diameter.csv"
EXPECTED_HEADER = [
    "", "t", "d^2 (mm^2)", "", "t", "dflame (mm)", "", "time ", "Q (W)",
    "time ", "Q (W)", "", "Model", "t", "d^2 (mm^2)", "dflame (mm)",
    "", "Model", "t", "Q (W)",
]
README_CONTEXT = {
    "fuel": "n-dodecane",
    "initial_diameter": {"raw_value": "4", "unit": "mm"},
    "pressure": {"raw_value": "1", "unit": "atm"},
    "mixture_mole_fractions_as_listed": {"XO2": "0.21", "XN2": "0.79"},
    "reference_doi": "10.1007/s12217-024-10115-x",
    "reference_figure": "Fig. 1",
    "readme_source_row": 13,
}

# Column indices are zero-based and refer to the exact raw CSV header above.
# Identical-looking Q blocks intentionally receive distinct series IDs.
SERIES = [
    {
        "series_id": "experiment_droplet_d_squared",
        "series_type": "experiment",
        "time_index": 1,
        "time_column": "t",
        "label_index": 0,
        "measurements": [(2, "d_squared", "mm^2")],
    },
    {
        "series_id": "experiment_flame_diameter",
        "series_type": "experiment",
        "time_index": 4,
        "time_column": "t",
        "label_index": 0,
        "measurements": [(5, "dflame", "mm")],
    },
    {
        "series_id": "experiment_Q_block_1",
        "series_type": "experiment",
        "time_index": 7,
        "time_column": "time",
        "label_index": 0,
        "measurements": [(8, "Q", "W")],
    },
    {
        "series_id": "experiment_Q_block_2",
        "series_type": "experiment",
        "time_index": 9,
        "time_column": "time",
        "label_index": 0,
        "measurements": [(10, "Q", "W")],
    },
    {
        "series_id": "model_diameter_and_flame",
        "series_type": "model",
        "time_index": 13,
        "time_column": "t",
        "label_index": 12,
        "measurements": [(14, "d_squared", "mm^2"), (15, "dflame", "mm")],
    },
    {
        "series_id": "model_Q",
        "series_type": "model",
        "time_index": 18,
        "time_column": "t",
        "label_index": 17,
        "measurements": [(19, "Q", "W")],
    },
]

SOURCE_PATH = RAW_DATA_DIR / INVESTIGATION_ID / SOURCE_NAME
SOURCE_RELATIVE_PATH = SOURCE_PATH.relative_to(RAW_DATA_DIR).as_posix()
OUTPUT_DIR = PROCESSED_DATA_DIR / "structured"
OUTPUT_PATH = OUTPUT_DIR / f"{INVESTIGATION_ID}_{DATASET_ID}_samples.jsonl"
REPORT_PATH = REPORTS_DIR / f"{INVESTIGATION_ID}_{DATASET_ID}_normalization_report.json"


def number(raw: str, *, row_number: int, column_name: str) -> float:
    try:
        parsed = Decimal(raw.strip())
        if not parsed.is_finite():
            raise InvalidOperation
        value = float(parsed)
        if not math.isfinite(value):
            raise InvalidOperation
        return value
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ValueError(
            f"Non-numeric value at CSV row {row_number}, column {column_name!r}: {raw!r}"
        ) from error


def make_record(row: list[str], row_number: int, series: dict[str, Any]) -> dict[str, Any] | None:
    time_raw = row[series["time_index"]].strip()
    measurement_values = [
        (index, name, unit, row[index].strip())
        for index, name, unit in series["measurements"]
        if row[index].strip()
    ]
    if not time_raw and not measurement_values:
        return None
    if not time_raw:
        raise ValueError(f"Missing time at CSV row {row_number}, series {series['series_id']}.")
    if not measurement_values:
        raise ValueError(f"Missing measurements at CSV row {row_number}, series {series['series_id']}.")

    measurements = []
    for index, name, unit, raw_value in measurement_values:
        measurements.append(
            {
                "name": name,
                "source_column": EXPECTED_HEADER[index].strip(),
                "value": number(raw_value, row_number=row_number, column_name=EXPECTED_HEADER[index]),
                "raw_value": raw_value,
                "unit": unit,
            }
        )

    identity = "|".join([INVESTIGATION_ID, SOURCE_RELATIVE_PATH, str(row_number), series["series_id"]])
    context_label = row[series["label_index"]].strip() or None
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
        "record_type": "time_series_sample",
        "investigation_id": INVESTIGATION_ID,
        "dataset_id": DATASET_ID,
        "series_id": series["series_id"],
        "series_type": series["series_type"],
        "time": {
            "name": series["time_column"],
            "value": number(time_raw, row_number=row_number, column_name=series["time_column"]),
            "raw_value": time_raw,
            "unit": None,
        },
        "measurements": measurements,
        "source_context_label_raw": context_label,
        "conditions": README_CONTEXT,
        "source_file": SOURCE_NAME,
        "source_relative_path": SOURCE_RELATIVE_PATH,
        "source_row_number": row_number,
        "source_columns": [
            *([EXPECTED_HEADER[series["label_index"]].strip()] if series["series_type"] == "model" else []),
            EXPECTED_HEADER[series["time_index"]].strip(),
            *[EXPECTED_HEADER[index].strip() for index, _, _ in series["measurements"]],
        ],
        "normalization_method": "explicit_independent_block_mapping",
    }


def normalize() -> dict[str, Any]:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Source CSV not found: {SOURCE_PATH}")

    records: list[dict[str, Any]] = []
    samples_by_series = {series["series_id"]: 0 for series in SERIES}
    source_data_rows = 0
    empty_rows_skipped = 0
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if header != EXPECTED_HEADER:
            raise ValueError(
                "Unexpected Burning history CSV header. No output was written.\n"
                f"Expected: {EXPECTED_HEADER!r}\nReceived: {header!r}"
            )

        for row_number, raw_row in enumerate(reader, start=2):
            if len(raw_row) > len(EXPECTED_HEADER):
                raise ValueError(f"CSV row {row_number} has {len(raw_row)} fields; expected at most 20.")
            row = (raw_row + [""] * len(EXPECTED_HEADER))[: len(EXPECTED_HEADER)]
            row_records = []
            for series in SERIES:
                record = make_record(row, row_number, series)
                if record is not None:
                    row_records.append(record)
                    samples_by_series[series["series_id"]] += 1
            if row_records:
                source_data_rows += 1
            else:
                empty_rows_skipped += 1
            records.extend(row_records)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(".jsonl.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary_path.replace(OUTPUT_PATH)

    report = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "source": SOURCE_RELATIVE_PATH,
        "output": OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "summary": {
            "source_data_rows": source_data_rows,
            "normalized_series_samples": len(records),
            "empty_rows_skipped": empty_rows_skipped,
            "samples_by_series": samples_by_series,
        },
        "notes": [
            "Each horizontal CSV block is mapped independently; physical row alignment across blocks is not treated as scientific pairing.",
            "Time units are not stated in the CSV and remain null pending authoritative source verification.",
            "The Q blocks remain separate because their repeated headers do not establish that they are duplicates.",
            "Sparse Model label cells are retained as raw row labels and are not forward-filled or interpreted.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = normalize()
    print(f"Structured samples: {OUTPUT_PATH}")
    print(json.dumps(result["summary"], indent=2))
    print(f"Normalization report: {REPORT_PATH}")
