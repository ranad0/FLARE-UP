"""Normalize the PSI-117 MST_2024_Dext side-by-side CSV into tidy observations.

The raw CSV is never modified. Each numeric measurement becomes one JSONL
record with its original file and physical CSV row for auditability.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import PROJECT_ROOT, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION


INVESTIGATION_ID = "PSI-117"
DATASET_ID = "MST_2024_Dext"
SOURCE_NAME = "PSI-117_Analyzed Data_MST_2024_Dext.csv"
EXPECTED_HEADER = [
    "Model", "Pressure", "Dext_cool", "Dext_hot", "", "Expt", "Pressure", "Dext_cool_Expt"
]
README_CONTEXT = {
    "fuel": "n-dodecane",
    "initial_diameter": {"raw_value": "4", "unit": "mm"},
    "mixture_mole_fractions_as_listed": {"XO2": "0.21", "XN2": "0.79"},
    "pressure_range_atm_listed_in_readme": [0.5, 1.5],
    "reference_doi": "10.1007/s12217-024-10115-x",
    "reference_figure": "Fig. 5",
    "readme_source_row": 14,
}

SOURCE_PATH = RAW_DATA_DIR / INVESTIGATION_ID / SOURCE_NAME
SOURCE_RELATIVE_PATH = SOURCE_PATH.relative_to(RAW_DATA_DIR).as_posix()
OUTPUT_DIR = PROCESSED_DATA_DIR / "structured"
OUTPUT_PATH = OUTPUT_DIR / f"{INVESTIGATION_ID}_{DATASET_ID}_observations.jsonl"
REPORT_PATH = REPORTS_DIR / f"{INVESTIGATION_ID}_{DATASET_ID}_normalization_report.json"


def parse_number(raw_value: str, *, row_number: int, column_name: str) -> float:
    try:
        return float(Decimal(raw_value.strip()))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(
            f"Expected a numeric value in CSV row {row_number}, column {column_name!r}: {raw_value!r}"
        ) from error


def make_observation(
    *, row_number: int, series_type: str, pressure_raw: str, quantity_name: str, value_raw: str
) -> dict[str, Any]:
    pressure = parse_number(pressure_raw, row_number=row_number, column_name="Pressure")
    value = parse_number(value_raw, row_number=row_number, column_name=quantity_name)
    pressure_range = README_CONTEXT["pressure_range_atm_listed_in_readme"]
    flags: list[str] = []
    if not pressure_range[0] <= pressure <= pressure_range[1]:
        flags.append("pressure_outside_readme_range_review")

    identity = "|".join(
        [INVESTIGATION_ID, SOURCE_RELATIVE_PATH, str(row_number), series_type, quantity_name]
    )
    record_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "record_type": "numeric_observation",
        "investigation_id": INVESTIGATION_ID,
        "dataset_id": DATASET_ID,
        "series_type": series_type,
        "quantity_name": quantity_name,
        "value": value,
        "value_raw": value_raw.strip(),
        "value_unit": None,
        "pressure_atm": pressure,
        "pressure_raw": pressure_raw.strip(),
        "conditions": README_CONTEXT,
        "source_file": SOURCE_NAME,
        "source_relative_path": SOURCE_RELATIVE_PATH,
        "source_row_number": row_number,
        "source_column_name": quantity_name,
        "quality_flags": flags,
        "normalization_method": "explicit_side_by_side_model_experiment_mapping",
    }


def normalize() -> dict[str, Any]:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Source CSV not found: {SOURCE_PATH}")

    records: list[dict[str, Any]] = []
    series_rows = {"model": 0, "experiment": 0}
    skipped_empty_rows = 0
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if header != EXPECTED_HEADER:
            raise ValueError(
                "Unexpected Dext CSV header. No output was written.\n"
                f"Expected: {EXPECTED_HEADER!r}\nReceived: {header!r}"
            )

        for row_number, row in enumerate(reader, start=2):
            row = (row + [""] * len(EXPECTED_HEADER))[: len(EXPECTED_HEADER)]
            model_values = [row[index].strip() for index in (1, 2, 3)]
            experiment_values = [row[index].strip() for index in (6, 7)]
            row_had_data = False

            if any(model_values):
                row_had_data = True
                pressure_raw, cool_raw, hot_raw = model_values
                if not pressure_raw:
                    raise ValueError(f"Missing model pressure in CSV row {row_number}.")
                series_rows["model"] += 1
                for quantity_name, value_raw in (
                    ("Dext_cool", cool_raw),
                    ("Dext_hot", hot_raw),
                ):
                    if value_raw:
                        records.append(
                            make_observation(
                                row_number=row_number,
                                series_type="model",
                                pressure_raw=pressure_raw,
                                quantity_name=quantity_name,
                                value_raw=value_raw,
                            )
                        )

            if any(experiment_values):
                row_had_data = True
                pressure_raw, cool_raw = experiment_values
                if not pressure_raw:
                    raise ValueError(f"Missing experiment pressure in CSV row {row_number}.")
                series_rows["experiment"] += 1
                if cool_raw:
                    records.append(
                        make_observation(
                            row_number=row_number,
                            series_type="experiment",
                            pressure_raw=pressure_raw,
                            quantity_name="Dext_cool_Expt",
                            value_raw=cool_raw,
                        )
                    )

            if not row_had_data:
                skipped_empty_rows += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(".jsonl.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary_path.replace(OUTPUT_PATH)

    flagged_records = [record["record_id"] for record in records if record["quality_flags"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "source": SOURCE_RELATIVE_PATH,
        "output": OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "summary": {
            "normalized_measurement_records": len(records),
            "model_source_rows": series_rows["model"],
            "experiment_source_rows": series_rows["experiment"],
            "empty_rows_skipped": skipped_empty_rows,
            "records_flagged_for_review": len(flagged_records),
        },
        "review_record_ids": flagged_records,
        "notes": [
            "Raw values are retained alongside numeric values; the raw CSV is not modified.",
            "Dext units were not found in the CSV header, so value_unit is null pending source verification.",
            "Pressure points outside the ReadMe range are retained and flagged, not discarded.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = normalize()
    print(f"Structured observations: {OUTPUT_PATH}")
    print(json.dumps(result["summary"], indent=2))
    print(f"Normalization report: {REPORT_PATH}")
