"""Read and update provenance metadata for URL-ingested raw files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from data_contract import SCHEMA_VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "data" / "shared" / "source_registry.json"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"schema_version": SCHEMA_VERSION, "sources": {}}
    # PowerShell's Set-Content -Encoding utf8 may add a BOM; tolerate it so a
    # registry repaired or inspected in PowerShell remains readable in Python.
    with REGISTRY_PATH.open("r", encoding="utf-8-sig") as source:
        value = json.load(source)
    if not isinstance(value, dict) or not isinstance(value.get("sources"), dict):
        raise ValueError(f"Invalid source registry: {REGISTRY_PATH}")
    value["schema_version"] = SCHEMA_VERSION
    return value


def save_registry(registry: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRY_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REGISTRY_PATH)


def origin_for(relative_raw_path: str) -> dict[str, Any] | None:
    return load_registry()["sources"].get(relative_raw_path)


def enrich_jsonl(output_path: Path, origin: dict[str, Any] | None) -> None:
    if not origin:
        return
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with output_path.open("r", encoding="utf-8") as source, temporary.open(
        "w", encoding="utf-8", newline="\n"
    ) as output:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            record["source_origin"] = origin
            if (origin.get("investigation_id_status") == "verified"
                    and origin.get("canonical_investigation_id")
                    and origin.get("investigation_id_evidence_url")):
                record["investigation_id"] = origin["canonical_investigation_id"]
            record["source_folder_label"] = origin.get("source_folder_label")
            record["investigation_id_status"] = origin.get("investigation_id_status", "unknown")
            record["investigation_label"] = origin.get("source_group") or origin.get("source_folder_label")
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(output_path)
