"""Build a scoped, source-traceable RAG batch from the manual safety-case bundle.

Run from the project root:
    python src/process_safety_cases.py

Only data/raw/nasa-safety-cases is read. No linked source is downloaded.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw"
SOURCE_DIR = RAW_ROOT / "nasa-safety-cases"
OUTPUT_DIR = ROOT / "data" / "processed" / "nasa-safety-cases"
REPORT_DIR = ROOT / "reports"
SCHEMA_VERSION = "2.0.0"
SOURCE_CATEGORY = "nasa_safety_case_study"
TARGET_WORDS = 250
OVERLAP_WORDS = 35


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    payload = "\n".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def split_coherent(text: str, target_words: int = TARGET_WORDS,
                   overlap_words: int = OVERLAP_WORDS) -> list[str]:
    """Create overlapping windows within one case section or source page."""
    words = text.split()
    output: list[str] = []
    start = 0
    while start < len(words):
        stop = min(start + target_words, len(words))
        output.append(" ".join(words[start:stop]))
        if stop == len(words):
            break
        start = max(start + 1, stop - overlap_words)
    return output


def section_blocks(markdown: str) -> list[dict[str, Any]]:
    """Read ## case and ### evidence/context sections without Markdown dependencies."""
    blocks: list[dict[str, Any]] = []
    current_case: str | None = None
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        text = "\n".join(current.pop("lines")).strip()
        current["body"] = text
        if text:
            blocks.append(current)
        current = None

    for line in markdown.splitlines():
        match = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if match:
            flush()
            level, heading = len(match.group(1)), match.group(2)
            if level == 2:
                current_case = heading
                if heading.startswith("ملخص البحث والاسترجاع"):
                    current_case = None
                    continue
                current = {"level": 2, "heading": heading, "case_title": heading, "lines": []}
            else:
                current = {
                    "level": 3, "heading": heading,
                    "case_title": current_case, "lines": [],
                }
            continue
        if current is not None:
            current["lines"].append(line)
    flush()
    return blocks


def markdown_citations(text: str, source_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    references: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for match in re.finditer(r"\[([A-Za-z0-9-]+)\]\(([^)]+)\)", text):
        source_id, linked_target = match.group(1), match.group(2).strip()
        catalog = source_by_id.get(source_id, {})
        url = linked_target if linked_target.startswith(("https://", "http://")) else catalog.get("url")
        key = (source_id, url)
        if key in seen:
            continue
        seen.add(key)
        references.append({
            "source_id": source_id,
            "title": catalog.get("title"),
            "url": url,
            "local_file_reference": catalog.get("local_file"),
            "locator_text": None,
        })
    return list(dict.fromkeys(ref["source_id"] for ref in references)), references


def build_chunk(*, text: str, content_type: str, source_file: str,
                source_relative_path: str, source_hash: str,
                source_location: str, source_ids: list[str],
                citations: list[dict[str, Any]], source_category: str,
                case_id: str | None = None, case_title: str | None = None,
                evidence_type: str | None = None, section_heading: str | None = None,
                chunk_index: int = 1, source_id: str | None = None,
                source_page: int | None = None) -> dict[str, Any]:
    chunk_id = stable_id("chunk", source_relative_path, source_location, chunk_index, text)
    urls = list(dict.fromkeys(c["url"] for c in citations if c.get("url")))
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "chunk",
        "chunk_id": chunk_id,
        "content_type": content_type,
        "source_category": source_category,
        "case_id": case_id,
        "case_title": case_title,
        "evidence_type": evidence_type,
        "section_heading": section_heading,
        "source_id": source_id,
        "source_ids": source_ids,
        "source_file": source_file,
        "source_relative_path": source_relative_path,
        "source_sha256": source_hash,
        "source_location": source_location,
        "source_page_number": source_page,
        "citation_urls": urls,
        "citation_url": urls[0] if len(urls) == 1 else None,
        "citation_status": "linked" if urls else "source_id_locator_only",
        "text": text,
        "embedding_text": "\n".join(part for part in (
            f"Category: {source_category}",
            f"Case: {case_title}" if case_title else None,
            f"Record ID: {case_id}" if case_id else None,
            f"Evidence type: {evidence_type}" if evidence_type else None,
            f"Source ID: {', '.join(source_ids)}" if source_ids else None,
            f"Location: {source_location}",
            f"Section: {section_heading}" if section_heading else None,
            "Content:", text,
        ) if part),
        "provenance": {
            "source_category": source_category,
            "case_id": case_id,
            "source_id": source_id,
            "source_ids": source_ids,
            "source_file": source_file,
            "source_relative_path": source_relative_path,
            "source_sha256": source_hash,
            "source_location": source_location,
            "citation_urls": urls,
        },
    }
    record["provenance"].update({
        key: value for key, value in {
            "evidence_type": evidence_type,
            "source_page_number": source_page,
            "section_heading": section_heading,
        }.items() if value is not None
    })
    return record


def main() -> None:
    dashboard_path = SOURCE_DIR / "Safety_Dashboard_Data.json"
    curated_path = SOURCE_DIR / "safety_summary_for_rag.md"
    full_text_path = SOURCE_DIR / "safety_full_text.md"
    for required_path in (dashboard_path, curated_path, full_text_path):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required safety-case input missing: {required_path}")

    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8-sig"))
    if not isinstance(dashboard.get("records"), list) or not isinstance(dashboard.get("sources"), list):
        raise ValueError("Dashboard JSON must contain records and sources arrays.")
    source_by_id = {str(source["source_id"]): source for source in dashboard["sources"]}
    case_by_id = {str(case["record_id"]): case for case in dashboard["records"]}
    case_title_to_id: dict[str, str] = {}
    for case in dashboard["records"]:
        for title in (case.get("title"), case.get("record_id")):
            if title:
                case_title_to_id[str(title).casefold()] = str(case["record_id"])

    hashes = {path.name: sha256(path) for path in (dashboard_path, curated_path, full_text_path)}
    citations_missing_url: set[str] = set()
    unknown_source_ids: set[str] = set()
    local_source_refs: list[dict[str, Any]] = []
    source_catalog_rows: list[dict[str, Any]] = []
    for source in dashboard["sources"]:
        local_file = source.get("local_file")
        local_path = (SOURCE_DIR / local_file).resolve() if local_file else None
        in_raw_root = bool(local_path and local_path == RAW_ROOT.resolve() or local_path and RAW_ROOT.resolve() in local_path.parents)
        exists = bool(local_path and in_raw_root and local_path.is_file())
        row = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "safety_case_source",
            "source_category": SOURCE_CATEGORY,
            "source_key": "nasa-safety-cases",
            "source_id": source.get("source_id"),
            "title": source.get("title"),
            "source_url": source.get("url"),
            "citation_url": source.get("url"),
            "local_file_reference": local_file,
            "local_file_available": exists if local_file else None,
            "source_origin_kind": "external_url" if source.get("url") else ("local_file" if local_file else "unresolved"),
        }
        source_catalog_rows.append(row)
        if local_file and not exists:
            local_source_refs.append({"source_id": source.get("source_id"), "local_file_reference": local_file})
        if not source.get("url"):
            citations_missing_url.add(str(source.get("source_id")))

    # Register only this manual bundle; it is a safety-case source, never a PSI ID.
    registry_path = ROOT / "data" / "shared" / "source_registry.json"
    if registry_path.is_file():
        registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    else:
        registry = {"schema_version": SCHEMA_VERSION, "sources": {}}
    registry_sources = registry.setdefault("sources", {})
    for name in ("Safety_Dashboard_Data.json", "safety_full_text.md", "safety_overview.md",
                 "Safety_Scientific_Summary.md", "safety_summary_for_rag.md"):
        path = SOURCE_DIR / name
        relative = path.relative_to(RAW_ROOT).as_posix()
        registry_sources[relative] = {
            "schema_version": SCHEMA_VERSION,
            "source_key": "nasa-safety-cases",
            "source_type": "manual_compiled_safety_case_bundle",
            "source_group": "nasa-safety-cases",
            "source_folder_label": "nasa-safety-cases",
            "source_category": SOURCE_CATEGORY,
            "canonical_investigation_id": None,
            "investigation_id_status": "not_applicable",
            "investigation_id_evidence_url": None,
            "source_url": None,
            "citation_url": None,
            "original_filename": path.name,
            "sha256": sha256(path),
            "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        }
    registry["schema_version"] = SCHEMA_VERSION
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_tmp = registry_path.with_suffix(".json.tmp")
    registry_tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry_tmp.replace(registry_path)

    # Keep records, evidence claims and historical/specification values separate.
    cases_out: list[dict[str, Any]] = []
    evidence_out: list[dict[str, Any]] = []
    measurements_out: list[dict[str, Any]] = []
    for case in dashboard["records"]:
        case_id = str(case["record_id"])
        cases_out.append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "safety_case_record",
            "source_category": SOURCE_CATEGORY,
            "source_key": "nasa-safety-cases",
            "case_id": case_id,
            "case_title": case.get("title"),
            "case_type": case.get("record_type"),
            "psi_id": None,
            "model_fit_eligible": False,
            "source_file": dashboard_path.name,
            "source_relative_path": dashboard_path.relative_to(RAW_ROOT).as_posix(),
            "source_sha256": hashes[dashboard_path.name],
            "source_location": f"records[{case_id}]",
            "citation_urls": [],
            "case_data": case,
        })
        for evidence_index, evidence in enumerate(case.get("evidence") or [], start=1):
            source_refs = evidence.get("sources") or []
            ids = [str(item.get("source_id")) for item in source_refs if item.get("source_id")]
            unknown_source_ids.update(source_id for source_id in ids if source_id not in source_by_id)
            refs = [{
                "source_id": item.get("source_id"),
                "title": source_by_id.get(str(item.get("source_id")), {}).get("title"),
                "url": source_by_id.get(str(item.get("source_id")), {}).get("url"),
                "local_file_reference": source_by_id.get(str(item.get("source_id")), {}).get("local_file"),
                "locator_text": item.get("locator"),
            } for item in source_refs]
            evidence_out.append({
                "schema_version": SCHEMA_VERSION,
                "record_type": "safety_evidence_claim",
                "source_category": SOURCE_CATEGORY,
                "case_id": case_id,
                "case_title": case.get("title"),
                "evidence_index": evidence_index,
                "evidence_type": evidence.get("evidence_type"),
                "statement": evidence.get("statement"),
                "source_ids": ids,
                "sources": refs,
                "citation_urls": list(dict.fromkeys(x["url"] for x in refs if x.get("url"))),
                "source_file": dashboard_path.name,
                "source_relative_path": dashboard_path.relative_to(RAW_ROOT).as_posix(),
                "source_sha256": hashes[dashboard_path.name],
                "source_location": f"records[{case_id}].evidence[{evidence_index - 1}]",
                "record_status": "curated_claim_with_source_locators",
                "model_fit_eligible": False,
            })
        for measurement_index, measurement in enumerate(case.get("measurements") or [], start=1):
            refs = measurement.get("sources") or []
            ids = [str(item.get("source_id")) for item in refs if item.get("source_id")]
            unknown_source_ids.update(source_id for source_id in ids if source_id not in source_by_id)
            measurements_out.append({
                "schema_version": SCHEMA_VERSION,
                "record_type": "safety_case_measurement",
                "source_category": SOURCE_CATEGORY,
                "case_id": case_id,
                "case_title": case.get("title"),
                "quantity_name": measurement.get("parameter"),
                "value": measurement.get("value"),
                "unit": measurement.get("unit"),
                "conditions": measurement.get("condition"),
                "evidence_type": measurement.get("evidence_type"),
                "source_ids": ids,
                "sources": [{
                    "source_id": item.get("source_id"),
                    "title": source_by_id.get(str(item.get("source_id")), {}).get("title"),
                    "url": source_by_id.get(str(item.get("source_id")), {}).get("url"),
                    "locator_text": item.get("locator"),
                } for item in refs],
                "source_file": dashboard_path.name,
                "source_relative_path": dashboard_path.relative_to(RAW_ROOT).as_posix(),
                "source_sha256": hashes[dashboard_path.name],
                "source_location": f"records[{case_id}].measurements[{measurement_index - 1}]",
                "record_status": "historical_or_hardware_value_not_flame_experiment_data",
                "psi_id": None,
                "model_fit_eligible": False,
                "quality_flags": [],
            })

    chunks: list[dict[str, Any]] = []
    section_blocks_found = section_blocks(curated_path.read_text(encoding="utf-8-sig"))
    summary_blocks = 0
    for block in section_blocks_found:
        body_lines = block["body"].splitlines()
        record_id_match = re.search(r"`record_id:\s*([^`]+)`", block["body"])
        type_match = re.search(r"`record_type:\s*([^`]+)`", block["body"])
        evidence_match = re.search(r"`evidence_type:\s*([^`]+)`", block["body"])
        case_id = record_id_match.group(1).strip() if record_id_match else None
        if not case_id and block.get("case_title"):
            normalized_title = str(block["case_title"]).casefold()
            case_id = next((cid for title, cid in case_title_to_id.items() if title in normalized_title or normalized_title in title), None)
        case = case_by_id.get(case_id or "", {})
        cleaned_lines = [line for line in body_lines if not re.search(r"`record_(?:id|type):", line)]
        text = "\n".join(cleaned_lines).strip()
        source_ids, refs = markdown_citations(text, source_by_id)
        unknown_source_ids.update(source_id for source_id in source_ids if source_id not in source_by_id)
        for source_id in source_ids:
            if not source_by_id.get(source_id, {}).get("url"):
                citations_missing_url.add(source_id)
        if not text:
            continue
        content_type = "safety_case_evidence" if evidence_match else "safety_case_context"
        location = f"section:{block['heading']}"
        for part_index, part in enumerate(split_coherent(text), start=1):
            chunks.append(build_chunk(
                text=part,
                content_type=content_type,
                source_file=curated_path.name,
                source_relative_path=curated_path.relative_to(RAW_ROOT).as_posix(),
                source_hash=hashes[curated_path.name],
                source_location=location,
                source_ids=source_ids,
                citations=refs,
                source_category=SOURCE_CATEGORY,
                case_id=case_id,
                case_title=case.get("title") or block.get("case_title"),
                evidence_type=evidence_match.group(1).strip() if evidence_match else None,
                section_heading=block["heading"],
                chunk_index=part_index,
            ))
            summary_blocks += 1

    # Full source excerpts are chunked within each explicitly marked PDF page.
    full_text = full_text_path.read_text(encoding="utf-8-sig")
    page_marker = re.compile(r"^<!-- source_id:\s*([^;]+);\s*PDF page\s+(\d+)\s*-->\s*$", re.MULTILINE)
    markers = list(page_marker.finditer(full_text))
    nonempty_pages = 0
    empty_pages = 0
    for index, marker in enumerate(markers):
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(full_text)
        raw_page_text = full_text[marker.end():stop]
        source_id = marker.group(1).strip()
        page_number = int(marker.group(2))
        page_text = raw_page_text.strip()
        page_text = re.sub(r"^##\s+[^\n]+\n", "", page_text, count=1).strip()
        if not page_text or page_text.casefold() in {"[no extractable text]", "no extractable text"}:
            empty_pages += 1
            continue
        nonempty_pages += 1
        source = source_by_id.get(source_id, {})
        if source_id not in source_by_id:
            unknown_source_ids.add(source_id)
        if not source.get("url"):
            citations_missing_url.add(source_id)
        refs = [{
            "source_id": source_id,
            "title": source.get("title"),
            "url": source.get("url"),
            "local_file_reference": source.get("local_file"),
            "locator_text": f"PDF page {page_number}",
        }]
        case_ids = [case_id for case_id, case in case_by_id.items() if source_id in case.get("source_references", [])]
        for part_index, part in enumerate(split_coherent(page_text), start=1):
            chunks.append(build_chunk(
                text=part,
                content_type="source_excerpt",
                source_file=full_text_path.name,
                source_relative_path=full_text_path.relative_to(RAW_ROOT).as_posix(),
                source_hash=hashes[full_text_path.name],
                source_location=f"source:{source_id};pdf_page:{page_number}",
                source_ids=[source_id],
                citations=refs,
                source_category=SOURCE_CATEGORY,
                case_id=case_ids[0] if len(case_ids) == 1 else None,
                case_title=case_by_id[case_ids[0]].get("title") if len(case_ids) == 1 else None,
                section_heading=source.get("title"),
                chunk_index=part_index,
                source_id=source_id,
                source_page=page_number,
            ))

    # Detect exact duplicate text but retain each source location for citation integrity.
    seen_text: set[tuple[str, str]] = set()
    duplicate_chunks = 0
    for chunk in chunks:
        key = (chunk["content_type"], re.sub(r"\s+", " ", chunk["text"]).strip().casefold())
        if key in seen_text:
            duplicate_chunks += 1
        seen_text.add(key)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_rows = {
        "cases.jsonl": cases_out,
        "evidence.jsonl": evidence_out,
        "measurements.jsonl": measurements_out,
        "source_catalog.jsonl": source_catalog_rows,
        "chunks.jsonl": chunks,
    }
    manifest_files: list[dict[str, Any]] = []
    for name, rows in output_rows.items():
        path = OUTPUT_DIR / name
        write_jsonl(path, rows)
        record_types: dict[str, int] = {}
        for row in rows:
            kind = str(row.get("record_type") or "unknown")
            record_types[kind] = record_types.get(kind, 0) + 1
        manifest_files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "record_count": len(rows),
            "record_types": record_types,
            "schema_version": SCHEMA_VERSION,
            "retrieval_role": "text_chunks" if name == "chunks.jsonl" else ("structured_lookup" if name != "source_catalog.jsonl" else "citation_catalog"),
        })

    errors: list[dict[str, Any]] = []
    missing_provenance: list[str] = []
    empty_chunk_ids = [row.get("chunk_id") for row in chunks if not str(row.get("text") or "").strip()]
    duplicate_ids = len({row.get("chunk_id") for row in chunks}) != len(chunks)
    for row in chunks:
        for field in ("chunk_id", "source_file", "source_relative_path", "source_sha256", "source_location", "source_category", "provenance"):
            if row.get(field) in (None, "", {}):
                missing_provenance.append(f"{row.get('chunk_id')}:{field}")
    for row in evidence_out:
        for source_id in row["source_ids"]:
            if source_id not in source_by_id:
                errors.append({"type": "unknown_source_id", "source_id": source_id, "record_id": row.get("record_id")})
    for row in measurements_out:
        if row.get("value") is None or row.get("quantity_name") is None:
            errors.append({"type": "measurement_missing_value_or_quantity", "source_location": row.get("source_location")})

    raw_inputs = [
        "Safety_Dashboard_Data.json", "safety_summary_for_rag.md", "safety_full_text.md",
        "safety_overview.md", "Safety_Scientific_Summary.md",
    ]
    excluded_inputs = [
        {"path": "data/raw/nasa-safety-cases/safety_overview.md", "reason": "Short navigation overview; overlaps the curated RAG summary."},
        {"path": "data/raw/nasa-safety-cases/Safety_Scientific_Summary.md", "reason": "Long derivative summary; overlaps the claim-level RAG summary and source excerpts."},
    ]
    qa = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": "safety-case-bundle-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_category": SOURCE_CATEGORY,
        "status": "valid_with_source_review_flags" if not errors and not empty_chunk_ids and not missing_provenance and not duplicate_ids else "invalid",
        "summary": {
            "case_records": len(cases_out),
            "evidence_claims": len(evidence_out),
            "historical_or_hardware_values": len(measurements_out),
            "source_catalog_entries": len(source_catalog_rows),
            "chunks": len(chunks),
            "curated_summary_chunks": sum(c["content_type"] != "source_excerpt" for c in chunks),
            "source_excerpt_chunks": sum(c["content_type"] == "source_excerpt" for c in chunks),
            "full_text_page_markers": len(markers),
            "nonempty_source_pages": nonempty_pages,
            "empty_source_pages_skipped": empty_pages,
            "exact_duplicate_chunks_preserved_for_provenance": duplicate_chunks,
            "empty_chunks": len(empty_chunk_ids),
            "duplicate_chunk_ids": duplicate_ids,
            "missing_provenance_fields": len(missing_provenance),
            "unknown_source_ids": len(unknown_source_ids),
            "catalog_sources_without_url": len(citations_missing_url),
            "catalog_local_files_missing": len(local_source_refs),
            "psi_experimental_records": 0,
        },
        "errors": errors,
        "missing_provenance": missing_provenance,
        "review_flags": {
            "source_ids_without_direct_url": sorted(citations_missing_url),
            "referenced_local_source_files_not_in_bundle": local_source_refs,
            "excluded_derivative_inputs": excluded_inputs,
            "exact_duplicate_chunks_preserved": duplicate_chunks,
            "note": "Local source files and URLs are never inferred or downloaded. Evidence may retain a source ID and locator without a direct link.",
        },
    }
    qa_path = REPORT_DIR / "qa_report_nasa-safety-cases.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": stable_id("batch", SOURCE_CATEGORY, *(entry["sha256"] for entry in manifest_files)),
        "created_at_utc": qa["generated_at_utc"],
        "status": qa["status"],
        "source_category": SOURCE_CATEGORY,
        "source_key": "nasa-safety-cases",
        "psi_investigation_id": None,
        "source_url_policy": "Per-claim citations are mapped only from the supplied source catalog and explicit Markdown links.",
        "inputs": [
            {"path": f"data/raw/nasa-safety-cases/{name}", "sha256": sha256(SOURCE_DIR / name),
             "retrieval_role": "curated_rag_input" if name == "safety_summary_for_rag.md" else ("source_text_input" if name == "safety_full_text.md" else "structured_input" if name == "Safety_Dashboard_Data.json" else "excluded_derivative")}
            for name in raw_inputs
        ],
        "files": manifest_files,
        "qa_report": qa_path.relative_to(ROOT).as_posix(),
    }
    manifest_path = REPORT_DIR / "batch_manifest_nasa-safety-cases.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batch_id": manifest["batch_id"], "status": qa["status"], "summary": qa["summary"],
                      "outputs": [entry["path"] for entry in manifest_files],
                      "manifest": manifest_path.as_posix(), "qa_report": qa_path.as_posix()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
