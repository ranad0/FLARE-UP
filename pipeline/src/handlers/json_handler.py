"""Preserve JSON/JSONL records and expose labeled scalar fields for search."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR


def _searchable_text(value: Any, prefix: str = "") -> str:
    pairs: list[str] = []
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    else:
        return f"{prefix}: {value}" if prefix and value is not None else ""
    for key, child in items:
        label = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, (dict, list)):
            nested = _searchable_text(child, label)
            if nested:
                pairs.extend(nested.splitlines())
        elif child is not None:
            pairs.append(f"{label}: {child}")
    return "\n".join(pairs)


def handle_json(source_path: Path) -> tuple[Path, int]:
    relative = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.suffix.lower() == ".jsonl":
        values = []
        with source_path.open("r", encoding="utf-8-sig") as source:
            for line_no, line in enumerate(source, start=1):
                if line.strip():
                    try:
                        values.append(json.loads(line))
                    except json.JSONDecodeError as error:
                        raise ValueError(f"Invalid JSONL at line {line_no}: {error}") from error
    else:
        value = json.loads(source_path.read_text(encoding="utf-8-sig"))
        values = value if isinstance(value, list) else [value]
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for index, value in enumerate(values, start=1):
            record = {
                "record_type": "structured_json", "source_file": source_path.name,
                "source_relative_path": relative.as_posix(), "investigation_id": None,
                "item_index": index, "data": value, "text": _searchable_text(value),
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path, len(values)
