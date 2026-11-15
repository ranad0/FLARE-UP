"""Create citation-ready text chunks from the normalized handler JSONL files.

Run from the project root with:
    python src/chunking.py

Numeric CSV/Excel rows remain structured records. This module only creates
searchable chunks from PDF pages, TXT/JSON documents, captions, and dataset indexes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import PROCESSED_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION


CHUNKS_PATH = PROCESSED_DATA_DIR / "chunks.jsonl"
REPORT_PATH = REPORTS_DIR / "chunking_report.json"
DEFAULT_TARGET_WORDS = 250
DEFAULT_OVERLAP_WORDS = 40
CHUNK_SCHEMA_VERSION = SCHEMA_VERSION

README_MARKERS = {"fuel", "do (mm)", "p (atm)", "data file", "reference"}


def normalize_text(value: str) -> str:
    """Normalize whitespace without changing the source record itself."""
    lines = [line.strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs).strip()


def format_timestamp(seconds: float) -> str:
    millis = round(max(0.0, seconds) * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def split_text(text: str, target_words: int, overlap_words: int) -> list[str]:
    """Split a single page/document into overlapping word windows.

    Pages are processed independently so a chunk never crosses a citation
    location. Word counts are a temporary proxy until the embedding model is
    selected and its tokenizer is available.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap_words

    return chunks


def stable_chunk_id(
    investigation_id: str,
    source_relative_path: str,
    source_location: str,
    chunk_index: int,
    text: str,
) -> str:
    identity = "\n".join(
        [investigation_id, source_relative_path, source_location, str(chunk_index), text]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def make_chunk(
    *,
    record: dict[str, Any],
    text: str,
    chunk_index: int,
    source_record_type: str,
    source_location: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_investigation_id = record.get("investigation_id")
    investigation_id = raw_investigation_id if record.get("investigation_id_status") == "verified" else None
    investigation_label = record.get("investigation_label") or (
        raw_investigation_id if raw_investigation_id not in (None, "", "unassigned") else None
    )
    id_status = record.get("investigation_id_status") or ("unverified" if investigation_label else "unknown")
    source_relative_path = str(record.get("source_relative_path") or record.get("source_file") or "unknown")
    source_file = str(record.get("source_file") or Path(source_relative_path).name)

    context_lines = [
        (f"Investigation ID: {investigation_id}" if investigation_id else f"Investigation label ({id_status}): {investigation_label or 'unknown'}"),
        f"Source file: {source_file}",
    ]
    if record.get("page_number") is not None:
        context_lines.append(f"Page: {record['page_number']}")
    if record.get("sheet_name"):
        context_lines.append(f"Sheet: {record['sheet_name']}")
    if record.get("row_number") is not None:
        context_lines.append(f"Source row: {record['row_number']}")
    if extra_metadata and extra_metadata.get("page_heading"):
        context_lines.append(f"Page heading: {extra_metadata['page_heading']}")

    chunk: dict[str, Any] = {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "record_type": "chunk",
        "chunk_id": stable_chunk_id(
            str(investigation_id or investigation_label or "unknown"),
            source_relative_path,
            source_location,
            chunk_index,
            text,
        ),
        "investigation_id": investigation_id,
        "investigation_label": investigation_label,
        "investigation_id_status": id_status,
        "source_file": source_file,
        "source_relative_path": source_relative_path,
        "source_record_type": source_record_type,
        "content_type": "scientific_text",
        "chunk_index": chunk_index,
        "source_location": source_location,
        "text": text,
        "embedding_text": "\n".join(context_lines) + "\n\nContent:\n" + text,
    }

    if record.get("source_origin") is not None:
        chunk["source_origin"] = record["source_origin"]
    # PSI-159 i_Investigation metadata contains one study DOI and multiple
    # publication DOIs; do not copy a document-level DOI onto every chunk.
    if record.get("doi") is not None and str(record.get("investigation_id") or "").upper() != "PSI-159":
        chunk["doi"] = record["doi"]
    if record.get("citation_url") is not None:
        chunk["citation_url"] = record["citation_url"]
    if record.get("source_folder_label") is not None:
        chunk["source_folder_label"] = record["source_folder_label"]

    for field in ("page_number", "sheet_name", "row_number", "slide_number", "page_type_estimate", "image_references"):
        if record.get(field) is not None:
            chunk[field] = record[field]
    if extra_metadata:
        chunk.update(extra_metadata)
    return chunk


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path.name}:{line_number}: {error}") from error
            if isinstance(value, dict):
                yield value


def is_readme_header(values: list[Any]) -> bool:
    labels = {str(value).strip().lower() for value in values if value is not None and str(value).strip()}
    return len(labels & README_MARKERS) >= 2


def readme_row_to_text(values: list[Any], headers: list[Any]) -> str:
    pairs: list[str] = []
    for index, value in enumerate(values):
        if value is None or not str(value).strip():
            continue
        header = headers[index] if index < len(headers) else None
        header_text = str(header).strip() if header is not None else ""
        if header_text:
            pairs.append(f"{header_text}: {str(value).strip()}")
        else:
            pairs.append(f"Unlabeled column {index + 1}: {str(value).strip()}")
    if not pairs:
        return ""
    return "PSI ReadMe index entry. " + " | ".join(pairs)


def process_source_file(
    path: Path,
    target_words: int,
    overlap_words: int,
    stats: dict[str, int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    current_headers_by_sheet: dict[str, list[Any]] = {}
    source_context: dict[str, Any] = {}
    pending_transcript: list[dict[str, Any]] = []
    indexed_csv_sources: set[str] = set()

    def flush_transcript() -> None:
        nonlocal pending_transcript
        if not pending_transcript:
            return
        base = pending_transcript[0]
        video_url = (base.get("source_origin") or {}).get("video_url") if isinstance(base.get("source_origin"), dict) else None
        words: list[str] = []
        cue_ranges: list[tuple[int, int, dict[str, Any]]] = []
        for cue in pending_transcript:
            cue_words = str(cue.get("text") or "").split()
            start_at = len(words)
            words.extend(cue_words)
            cue_ranges.append((start_at, len(words), cue))
        cursor = 0
        chunk_index = 0
        while cursor < len(words):
            stop = min(cursor + target_words, len(words))
            selected = [cue for start_at, end_at, cue in cue_ranges if end_at > cursor and start_at < stop]
            if not selected:
                break
            chunk_index += 1
            start_seconds = float(selected[0].get("start_seconds", 0))
            end_seconds = float(selected[-1].get("end_seconds", start_seconds))
            text = " ".join(words[cursor:stop])
            start_stamp = format_timestamp(start_seconds)
            end_stamp = format_timestamp(end_seconds)
            output.append(make_chunk(
                record=base,
                text=text,
                chunk_index=chunk_index,
                source_record_type="transcript_segment",
                source_location=f"time:{start_stamp}-{end_stamp}",
                extra_metadata={
                    "content_type": "video_transcript",
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "video_url": video_url,
                    "citation_url": (base.get("source_origin") or {}).get("citation_url", video_url) if isinstance(base.get("source_origin"), dict) else video_url,
                    "cue_count": len(selected),
                },
            ))
            stats["chunks_created"] += 1
            stats["transcript_chunks_created"] = stats.get("transcript_chunks_created", 0) + 1
            cursor = stop if stop == len(words) else max(stop - overlap_words, cursor + 1)
        stats["transcript_segments_chunked"] = stats.get("transcript_segments_chunked", 0) + len(pending_transcript)
        pending_transcript = []

    for record_index, record in enumerate(read_jsonl(path), start=1):
        stats["records_seen"] += 1
        record_type = str(record.get("record_type") or "")

        # Excel row records do not repeat workbook-level source metadata.
        # Carry it forward so row citations and ReadMe detection stay traceable.
        if record.get("source_file"):
            source_context = {
                key: record[key]
                for key in ("source_file", "source_relative_path", "investigation_id", "source_origin", "source_folder_label")
                if record.get(key) is not None
            }
        elif source_context:
            record = {**source_context, **record}

        if record_type == "transcript_segment":
            pending_transcript.append(record)
            continue
        flush_transcript()

        if record_type == "workbook":
            source_name = str(record.get("source_file") or "Excel workbook")
            sheets = record.get("sheet_names") or []
            source_rel = Path(str(record.get("source_relative_path") or source_name))
            structured_path = (Path("data/processed") / source_rel).with_suffix(".jsonl").as_posix()
            text = (
                f"Dataset index for Excel workbook {source_name}. "
                f"Worksheets: {', '.join(str(sheet) for sheet in sheets) or 'not listed'}. "
                f"Original cell values and row locations are preserved separately in {structured_path}. "
                "This index describes the workbook structure and is not a measurement result."
            )
            output.append(make_chunk(
                record=record, text=normalize_text(text), chunk_index=1,
                source_record_type="workbook", source_location="workbook",
                extra_metadata={"content_type": "dataset_index", "sheet_names": sheets,
                                "structured_records_path": structured_path},
            ))
            stats["dataset_index_entries"] += 1
            stats["chunks_created"] += 1
            continue

        if record_type == "table":
            columns = record.get("columns") if isinstance(record.get("columns"), list) else []
            source_name = str(record.get("source_file") or record.get("table_name") or "CSV source")
            structured_path = f"data/processed/structured/{Path(source_name).stem}_observations.jsonl"
            source_location = "row:1"
            text = (
                f"Dataset index for experimental CSV table {source_name}. "
                f"Source columns: {', '.join(str(column) for column in columns if column is not None)}. "
                f"The source table rows are preserved separately. Numeric observation records, when available, are in {structured_path}. "
                "This index describes the table structure and is not a measurement result."
            )
            output.append(make_chunk(
                record=record,
                text=normalize_text(text),
                chunk_index=1,
                source_record_type="table",
                source_location=source_location,
                extra_metadata={
                    "content_type": "dataset_index",
                    "table_id": record.get("table_id"),
                    "source_columns": columns,
                    "structured_records_path": structured_path,
                },
            ))
            stats["dataset_index_entries"] += 1
            indexed_csv_sources.add(str(record.get("source_relative_path") or source_name))
            stats["csv_tables_indexed"] = stats.get("csv_tables_indexed", 0) + 1
            stats["chunks_created"] += 1
            continue

        if record_type in {"page", "text_document", "structured_json"}:
            source_text = normalize_text(str(record.get("text") or ""))
            if not source_text:
                stats["empty_text_records"] += 1
                continue

            heading = next(
                (line[:160] for line in source_text.splitlines() if line.strip()),
                None,
            )
            location = str(record.get("source_location") or (
                f"page:{record['page_number']}"
                if record.get("page_number") is not None
                else f"record:{record_index}"
            ))
            parts = split_text(source_text, target_words, overlap_words)
            for chunk_index, part in enumerate(parts, start=1):
                extra = {"page_heading": heading} if heading and record_type == "page" else None
                if record_type == "text_document":
                    extra = {key: record[key] for key in (
                        "section_heading", "paragraph_start", "paragraph_end", "slide_number", "image_references"
                    ) if record.get(key) is not None}
                if record_type == "structured_json":
                    extra = {**(extra or {}), "content_type": "structured_json_text", "item_index": record.get("item_index")}
                output.append(
                    make_chunk(
                        record=record,
                        text=part,
                        chunk_index=chunk_index,
                        source_record_type=record_type,
                        source_location=location,
                        extra_metadata=extra,
                    )
                )
            stats["text_records_chunked"] += 1
            stats["chunks_created"] += len(parts)
            continue

        is_csv_table_row = (
            (record_type in {"row", "table_row"} or not record_type)
            and isinstance(record.get("columns"), list)
            and str(record.get("source_file") or "").lower().endswith(".csv")
        )
        csv_source_key = str(record.get("source_relative_path") or record.get("source_file") or "unknown")
        if is_csv_table_row and csv_source_key not in indexed_csv_sources:
            columns = record.get("columns") or []
            source_name = str(record.get("source_file") or "CSV source")
            structured_path = f"data/processed/structured/{Path(source_name).stem}_observations.jsonl"
            text = (
                f"Dataset index for experimental CSV table {source_name}. "
                f"Source columns: {', '.join(str(column) for column in columns if column is not None)}. "
                f"The source table rows are preserved separately. Numeric observation records, when available, are in {structured_path}. "
                "This index describes the table structure and is not a measurement result."
            )
            index_record = {**record, "row_number": 1}
            output.append(make_chunk(
                record=index_record,
                text=normalize_text(text),
                chunk_index=1,
                source_record_type="table",
                source_location="row:1",
                extra_metadata={"content_type": "dataset_index", "source_columns": columns,
                                "structured_records_path": structured_path},
            ))
            indexed_csv_sources.add(csv_source_key)
            stats["dataset_index_entries"] += 1
            stats["csv_tables_indexed"] = stats.get("csv_tables_indexed", 0) + 1
            stats["chunks_created"] += 1

        is_excel_row = record_type in {"row", "table_row"} or (not record_type and isinstance(record.get("values"), list))
        is_readme_record = "readme" in str(record.get("source_file", "")).lower()

        if is_excel_row and is_readme_record:
            sheet = str(record.get("sheet_name") or "")
            values = record.get("values")
            if not isinstance(values, list):
                continue
            if is_readme_header(values):
                # The workbook repeats partial headers for table sections.
                # Carry forward labels in blank columns (e.g., Data File,
                # Reference, Figure) while allowing later labels to replace them.
                previous = current_headers_by_sheet.get(sheet, [])
                merged = list(values)
                for index, value in enumerate(merged):
                    if (value is None or not str(value).strip()) and index < len(previous):
                        merged[index] = previous[index]
                current_headers_by_sheet[sheet] = merged
                continue

            headers = current_headers_by_sheet.get(sheet)
            if headers is None:
                continue
            text = normalize_text(readme_row_to_text(values, headers))
            if not text:
                continue

            output.append(
                make_chunk(
                    record=record,
                    text=text,
                    chunk_index=1,
                    source_record_type="readme_row",
                    source_location=f"sheet:{sheet}:row:{record.get('row_number', record_index)}",
                    extra_metadata={"content_type": "dataset_index", "column_names": [str(h) if h is not None else "" for h in headers]},
                )
            )
            stats["dataset_index_entries"] += 1
            stats["chunks_created"] += 1
            continue

        if is_excel_row:
            # Numeric rows keep their columns and original values in the
            # handler output. The RAG layer should query these structurally.
            stats["structured_rows_preserved"] += 1

    flush_transcript()
    return output


def build_chunks(target_words: int, overlap_words: int, investigation_id: str | None = None,
                 source_prefix: str | None = None) -> dict[str, Any]:
    if target_words < 1:
        raise ValueError("--target-words must be greater than zero.")
    if overlap_words < 0 or overlap_words >= target_words:
        raise ValueError("--overlap-words must be between zero and target_words - 1.")
    if not PROCESSED_DATA_DIR.exists():
        raise FileNotFoundError(f"Processed data folder does not exist: {PROCESSED_DATA_DIR}")

    stats = {
        "source_files_seen": 0,
        "records_seen": 0,
        "text_records_chunked": 0,
        "transcript_segments_chunked": 0,
        "transcript_chunks_created": 0,
        "dataset_index_entries": 0,
        "csv_tables_indexed": 0,
        "structured_rows_preserved": 0,
        "empty_text_records": 0,
        "chunks_created": 0,
    }
    prefix_parts = tuple(Path(source_prefix.replace("\\", "/")).parts) if source_prefix else ()

    def matches_scope(path: Path) -> bool:
        parts = path.relative_to(PROCESSED_DATA_DIR).parts
        if investigation_id:
            return bool(parts) and (parts[0] == investigation_id
                or (path.parent.name == "structured" and path.name.startswith(f"{investigation_id}_")))
        if prefix_parts:
            return parts[:len(prefix_parts)] == prefix_parts
        return True

    source_files = sorted(
        path
        for path in PROCESSED_DATA_DIR.rglob("*.jsonl")
        if path.name.lower() != "chunks.jsonl" and "assets" not in {part.lower() for part in path.parts}
        and path.name.lower() != "s_psi-159.jsonl"
        and matches_scope(path)
    )

    all_chunks: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in source_files:
        stats["source_files_seen"] += 1
        try:
            all_chunks.extend(process_source_file(path, target_words, overlap_words, stats))
        except (OSError, ValueError, UnicodeError) as error:
            failures.append({"source": path.relative_to(PROCESSED_DATA_DIR).as_posix(), "error": str(error)})

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if investigation_id:
        chunks_path = PROCESSED_DATA_DIR / investigation_id / "chunks.jsonl"
    elif source_prefix:
        chunks_path = PROCESSED_DATA_DIR / Path(source_prefix.replace("\\", "/")) / "chunks.jsonl"
    else:
        chunks_path = CHUNKS_PATH
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = chunks_path.with_suffix(".jsonl.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
        for chunk in all_chunks:
            output.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    temporary_path.replace(chunks_path)

    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "chunking_method": "word_window_per_page_record_or_transcript_time_range",
        "target_words": target_words,
        "overlap_words": overlap_words,
        "output": chunks_path.relative_to(PROJECT_ROOT).as_posix(),
        "investigation_filter": investigation_id,
        "source_prefix_filter": source_prefix,
        "summary": stats,
        "failures": failures,
        "note": "Word counts are an initial proxy. Match chunk limits to the selected embedding model tokenizer before production RAG ingestion.",
    }
    scope_name = investigation_id or (source_prefix.replace("/", "_").replace("\\", "_") if source_prefix else None)
    report_path = REPORTS_DIR / (f"chunking_report_{scope_name}.json" if scope_name else REPORT_PATH.name)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create citation-ready RAG text chunks from processed JSONL.")
    parser.add_argument("--target-words", type=int, default=DEFAULT_TARGET_WORDS)
    parser.add_argument("--overlap-words", type=int, default=DEFAULT_OVERLAP_WORDS)
    parser.add_argument("--investigation", help="Write a standalone chunk batch for one investigation, e.g. PSI-159.")
    parser.add_argument("--source-prefix", help="Chunk only a relative processed folder, e.g. nasa-combustion-reference/bass.")
    args = parser.parse_args()

    if args.investigation and args.source_prefix:
        raise SystemExit("Choose either --investigation or --source-prefix.")
    investigation_id = args.investigation.upper() if args.investigation else None
    if investigation_id and not re.fullmatch(r"PSI-\d+", investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-159.")
    if args.source_prefix:
        parts = tuple(Path(args.source_prefix.replace("\\", "/")).parts)
        if not parts or parts[0] != "nasa-combustion-reference" or any(part in {".", ".."} for part in parts):
            raise SystemExit("--source-prefix must stay under nasa-combustion-reference.")
    report = build_chunks(args.target_words, args.overlap_words, investigation_id, args.source_prefix)
    summary = report["summary"]
    print(f"Chunk file: {report['output']}")
    print(f"Chunks created: {summary['chunks_created']}")
    print(f"Text records chunked: {summary['text_records_chunked']}")
    print(f"Dataset index entries: {summary['dataset_index_entries']}")
    print(f"Structured rows preserved: {summary['structured_rows_preserved']}")
    print(f"Failures: {len(report['failures'])}")
    scope_name = investigation_id or (args.source_prefix.replace("/", "_").replace("\\", "_") if args.source_prefix else None)
    report_name = f"chunking_report_{scope_name}.json" if scope_name else REPORT_PATH.name
    print(f"Chunking report: {REPORTS_DIR / report_name}")


if __name__ == "__main__":
    main()
