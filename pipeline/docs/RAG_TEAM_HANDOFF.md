# Flare Up — RAG Team Handoff

## Purpose

This document describes the handoff from the scientific data preparation pipeline to the RAG application. The pipeline parses files, preserves source provenance, normalizes selected measurements, and produces retrieval chunks. The RAG team owns indexing, retrieval, numeric querying, answer generation, evidence checks, citations, and abstention.

## Files to share

| Path | Role |
|---|---|
| `src/`, `config/settings.py`, `requirements.txt` | Processing code and dependencies. |
| `data/processed/chunks.jsonl` | Searchable text and dataset-index records. Embed `embedding_text`; retain other fields as metadata. |
| `data/processed/structured/PSI-117_MST_2024_Dext_observations.jsonl` | Normalized numeric observations. Query as structured data, not prose. |
| `data/processed/structured/PSI-117_MST_2024_Burning_history_Flame_diameter_samples.jsonl` | Normalized time-series observations (one quantity per record after finalization). Preserve series identity, time, and source row. |
| `data/processed/visual_annotations.jsonl` and referenced `data/processed/PSI-117/assets/` | Human-reviewed visual descriptions and extracted image assets. These are not digitized data. |
| `reports/`, `data/shared/` (when present) | QA, normalization, chunking reports, and source registry. |
| `docs/DATA_CONTRACT.md` | Normative v2.0.0 schema, provenance chain, review states, and batch acceptance. |
| `docs/source_ingestion.md` | How to acquire sources by direct URL and run the pipeline. |

Do not share `config/source_links.json` if it contains signed/private URLs. Use `config/source_links.example.json` as the shareable template. Raw source files can be shared separately through approved team storage when needed to validate citations or rerun processing.

Read `docs/DATA_CONTRACT.md` as the normative v2.0.0 field contract.

## Text retrieval contract

Each line of `chunks.jsonl` is one JSON object. Embed `embedding_text`; return `text` as the retrieved content. Store and return at least `chunk_id`, `investigation_id`, `investigation_label`, `investigation_id_status`, `document_id`, `source_file`, `source_relative_path`, `source_record_type`, `content_type`, `source_location`, `citation_url`, `doi`, and `provenance` as metadata. Preserve optional `source_origin`, `video_url`, page/sheet/row fields, image references, and quality flags.

Citation locations are represented as `page:N`, `sheet:<name>:row:N`, or (for transcript chunks) a timestamp range. Include the location with each cited claim. Dataset-index chunks describe where data may be found; they are not themselves measurement evidence.

Example of the finalized v2.0.0 shape (illustrative values):

```json
{
  "schema_version": "2.0.0",
  "record_type": "chunk",
  "chunk_id": "chunk_...",
  "investigation_id": null,
  "investigation_label": "PSI-117",
  "investigation_id_status": "unverified",
  "document_id": "doc_...",
  "source_file": "PSI-117_Analyzed Data_ReadMe_List_of_Data.xlsx",
  "source_record_type": "readme_row",
  "content_type": "dataset_index",
  "source_location": "sheet:Sheet1:row:2",
  "text": "PSI ReadMe index entry. Fuel: n-heptane | ...",
  "citation_url": "https://doi.org/10.1016/j.proci.2018.05.151",
  "doi": "10.1016/j.proci.2018.05.151",
  "embedding_text": "Investigation label (unverified): PSI-117\nSource file: ...",
  "provenance": {
    "investigation_id": null,
    "investigation_label": "PSI-117",
    "investigation_id_status": "unverified",
    "document_id": "doc_...",
    "source_location": "sheet:Sheet1:row:2"
  }
}
```

The workspace label `PSI-117` is not to be used as an authoritative ID until its canonical NASA catalog mapping is verified. Do not infer an official ID from a filename or folder name.

## Structured measurement contract

Keep numeric observations outside ordinary text chunks. Preserve fields such as `dataset_id`, `series_type` (model vs. experiment), `quantity_name`, `value`, `value_raw`, `value_unit`, `pressure_atm`, `conditions`, `source_file`, `source_row_number`, `source_column_name`, and `quality_flags`. A null unit means the pipeline did not establish one; do not invent a unit. Filter by dataset, quantity, conditions, and series before answering numerical questions, and cite the underlying source row(s).

## Evidence and answer behavior

1. Select text retrieval for explanatory questions and structured lookup for numerical questions; combine both when needed.
2. Distinguish measurements from model predictions. Do not infer measurements from a dataset index.
3. Cite factual scientific claims to file plus page, sheet/row, or video timestamp; retain DOI and source URLs when available.
4. Abstain or state what evidence is missing when units, conditions, source identity, or figure context are unclear.
5. Do not claim numerical figure values unless a separately validated digitization step produced them. Current visual annotations are descriptions only.

## Current status and limitations

The previous report recorded 45 chunks, 9 dataset-index entries, and 692 structured rows preserved. Those counts predate the current contract. The current contract version is 2.0.0; hand off a batch after `src/finalize_batch.py` writes a valid `reports/qa_report.json` and `reports/batch_manifest.json`.

URL ingestion expects direct HTTPS file links. ZIP extraction is safety-limited, and only file types registered in `src/main.py` are processed. YouTube video files are not downloaded: provide an authorized VTT/SRT transcript URL alongside the video URL. A video link alone cannot supply transcript text. The current PSI-117 label in the workspace is not yet confirmed as the canonical NASA catalog identity.

## Integration decisions to confirm

- Vector database, embedding model, metadata schema, and index update strategy.
- Separate query interface for normalized measurements and time series.
- Storage and return format for image assets.
- Citation object expected by the interface (source, page/row/time, URL).
- Evidence threshold and abstention behavior.
- Representative acceptance examples: PDF question, dataset discovery, numeric comparison, figure question, and a question that should abstain.

## Suggested handoff sequence

1. Share this document, code/dependencies, chunks, structured JSONL, visual annotations/assets, and reports.
2. Agree on the text and numeric data contracts above.
3. Regenerate the outputs with current code and reconcile schema/counts against reports.
4. Test representative questions end-to-end and verify that citations resolve to the source.
