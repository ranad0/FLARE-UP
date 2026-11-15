"""Shared stable identifiers and provenance contract for Flare Up batches."""
from __future__ import annotations
import hashlib
import re
from typing import Any

SCHEMA_VERSION = "2.0.0"
PIPELINE_VERSION = "0.2.0"


def stable_id(prefix: str, *parts: object) -> str:
    value = "\n".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


def doi_from(record: dict[str, Any], origin: dict[str, Any] | None) -> str | None:
    values = [record.get("doi"), record.get("reference_doi")]
    if isinstance(record.get("conditions"), dict):
        values.append(record["conditions"].get("reference_doi"))
    if origin:
        values.append(origin.get("doi"))
    for value in values:
        if value:
            return str(value).strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi_matches = [
        match.group(0).rstrip(".,;)]\"")
        for match in re.finditer(r"10\.\d{4,9}/[^\s|]+", str(record.get("text") or ""))
    ]
    if (record.get("record_type") == "chunk"
            and str(record.get("investigation_id") or "").upper() == "PSI-159"):
        # A PSI-159 chunk mentioning multiple DOIs has no single defensible DOI citation.
        unique_dois = list(dict.fromkeys(doi_matches))
        return unique_dois[0] if len(unique_dois) == 1 else None
    return doi_matches[0] if doi_matches else None


def apply_contract(record: dict[str, Any], source_relative_path: str,
                   source_file: str, source_sha256: str | None,
                   origin: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add common IDs and provenance; never promote folder labels to NASA IDs."""
    relative = source_relative_path.replace("\\", "/")
    old_id = record.get("investigation_id")
    label = ((origin or {}).get("source_group") or (origin or {}).get("source_folder_label")
             or record.get("investigation_label") or old_id
             or (relative.split("/")[0] if "/" in relative else None))
    label = str(label).strip() if label else None
    if label and label.lower() in {"unassigned", "unknown", "none", "null"}:
        label = None
    investigation_id, id_status = None, "unknown"
    if (origin and origin.get("investigation_id_status") == "verified"
            and origin.get("canonical_investigation_id")
            and origin.get("investigation_id_evidence_url")):
        investigation_id, id_status = str(origin["canonical_investigation_id"]), "verified"
    elif label:
        id_status = "unverified"

    document_id = stable_id("doc", relative, source_sha256 or "hash_unavailable")
    kind = record.get("record_type") or ("table_row" if "values" in record and "columns" in record else "record")
    location = record.get("source_location")
    if record.get("page_number") is not None:
        location = f"page:{record['page_number']}"
    elif record.get("sheet_name") and record.get("row_number") is not None:
        location = f"sheet:{record['sheet_name']}:row:{record['row_number']}"
    elif record.get("source_row_number") is not None:
        location = f"row:{record['source_row_number']}"
    elif record.get("start_seconds") is not None:
        location = f"time:{record['start_seconds']}-{record.get('end_seconds')}"

    doi = doi_from(record, origin)
    citation_url = record.get("citation_url") or (origin or {}).get("citation_url")
    if doi and not citation_url:
        citation_url = f"https://doi.org/{doi}"
    source_url = record.get("source_url") or (origin or {}).get("source_url") or (origin or {}).get("caption_source_url")
    record.update({
        "schema_version": SCHEMA_VERSION, "record_type": kind,
        "investigation_id": investigation_id, "investigation_label": label,
        "investigation_id_status": id_status, "document_id": document_id,
        "source_file": source_file, "source_relative_path": relative,
        "source_location": location, "source_sha256": source_sha256,
        "source_url": source_url, "citation_url": citation_url, "doi": doi,
    })

    id_key = {
        "page": "page_id", "table": "table_id",
        "row": "row_id", "table_row": "row_id", "readme_row": "row_id",
        "numeric_observation": "record_id", "time_series_sample": "record_id",
        "time_series_observation": "record_id", "transcript_segment": "segment_id",
        "figure_asset": "asset_id", "visual_annotation": "asset_id",
        "text_document": "text_record_id",
    }.get(str(kind))
    if id_key and not record.get(id_key):
        record[id_key] = stable_id(id_key.split("_")[0], document_id, location,
                                   record.get("chunk_index"), record.get("text"))
    if kind in {"row", "table_row", "readme_row"}:
        record.setdefault("table_id", stable_id("table", document_id, record.get("sheet_name") or "csv"))
    elif kind == "sheet" or record.get("sheet_name"):
        record.setdefault("table_id", stable_id("table", document_id, record.get("sheet_name") or "csv"))
    if kind == "page" and record.get("page_number") is not None:
        record["page_id"] = stable_id("page", document_id, record["page_number"])

    if kind in {"numeric_observation", "time_series_sample", "time_series_observation"}:
        if record.get("quantity_name") is not None:
            record.setdefault("variable", record["quantity_name"])
        if "unit" not in record:
            record["unit"] = record.get("value_unit")
        flags = list(record.get("quality_flags") or [])
        unit = record.get("unit", record.get("value_unit"))
        record["unit_status"] = "needs_review" if unit is None else "provided"
        if unit is None and "unit_missing_review" not in flags:
            flags.append("unit_missing_review")
        if id_status == "unverified" and "investigation_id_unverified" not in flags:
            flags.append("investigation_id_unverified")
        record["quality_flags"] = flags
        record["record_status"] = "needs_review" if flags else "validated_structure"

    chain_fields = (
        "investigation_id", "investigation_label", "investigation_id_status", "document_id",
        "page_id", "table_id", "row_id", "chunk_id", "record_id", "asset_id",
        "source_file", "source_relative_path", "source_location", "source_sha256",
        "source_url", "citation_url", "doi",
    )
    record["provenance"] = {key: record[key] for key in chain_fields if record.get(key) is not None}
    if origin:
        record["source_origin"] = origin
    return record
