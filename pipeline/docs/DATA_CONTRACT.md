# Flare Up Data Contract — v2.0.0

This contract is the interface between the Data Pipeline and RAG. Every
JSONL record in a batch finalized by `src/finalize_batch.py` carries
`schema_version: "2.0.0"`. A structural change requires a version change and a
new batch manifest. Never mix records from different schema versions in one
index without an explicit migration.

## Common fields and provenance

Every record carries `record_type`, `document_id`, `source_file`,
`source_relative_path`, `source_sha256`, `source_location`, `schema_version`,
`investigation_id`, `investigation_label`, and `investigation_id_status`, plus
`provenance`. URLs and DOI are present when available. `investigation_id` is
null unless a verified ID and its evidence URL are present in the source
registry. Folder names such as `PSI-117` remain `investigation_label` with
status `unverified`.

`provenance` links the investigation identity/status, document, page/table/row,
and leaf object (`chunk_id`, `record_id`, or `asset_id`) to the original path,
hash, locator, citation URL, and DOI. Stable IDs are SHA-256-derived from
source identity and locator so a rerun of an unchanged source retains IDs.

## Text chunks

`data/processed/chunks.jsonl` contains one text retrieval object per line:

- Required: `chunk_id`, `document_id`, `investigation_id` (nullable),
  `investigation_label`, `investigation_id_status`, `text`, `embedding_text`,
  `source_file`, `source_relative_path`, `source_location`, `content_type`,
  `schema_version`, and `provenance`.
- `source_location` uses `page:N`, `sheet:<name>:row:N`, `row:N`, or a
  timestamp range for video transcripts.
- Embed `embedding_text`; return `text` and source locators as citations.
- Preserve DOI, `citation_url`, `source_url`, page/sheet/row fields, image
  references, and `source_origin` when present.

## Structured measurements

Normalized measurements live in `data/processed/structured/*.jsonl`, separate
from text chunks. The finalizer emits one record per measurement variable. A
record has `record_id`, `dataset_id`, `series_type`, `quantity_name` and alias
`variable`, numeric `value`, `value_raw`, `unit`, `unit_status`, `conditions`,
`source_file`, `source_relative_path`, `source_row_number`, `source_location`,
`quality_flags`, `record_status`, and full provenance. Time-series observations
also carry `series_id` and `time` with raw/numeric value and its own
`time_unit_status`.

Null units are retained as null and marked `needs_review`; no unit is inferred.
`quality_flags` retains review reasons. Do not embed numeric samples as prose;
query them structurally and cite the source row/record.

## Figures and tables

PDF image extraction is represented by explicit `figure_asset` records with
`asset_id`, `document_id`, `page_id`, `page_number`, `image_reference`,
`figure_context`, `caption`, `caption_status`, and
`visual_interpretation_status`. Missing captions are null with
`caption_status: "needs_review"`; extraction is not scientific interpretation.
Human-authored `visual_annotations.jsonl` remain separate linked records.
No chart values become measurements without a recorded, validated
digitization workflow.

CSV data has a file-level `table` record and row-level `table_row` records.
Excel sheet and row records receive stable `table_id`/`row_id` plus sheet/row
locators. Raw table values remain available in handler outputs.

## Validation and batch delivery

Run the complete pipeline, ending with `python .\src\finalize_batch.py`.
It writes `reports/qa_report.json` and `reports/batch_manifest.json`. The QA
report checks required fields, schema consistency, image-file references,
measurement fields, and chunk citation locations. Scientific review flags
(unverified investigation labels, missing units/captions) are warnings that
must remain visible; they do not become guessed values. Do not index a batch
whose QA status is `invalid`.

The batch manifest lists processed JSONL files and image assets, hashes,
record counts/types, schema version, and QA status. The separate
`reports/manifest.csv` inventories raw files and uses `investigation_label` plus
`investigation_id_status` instead of treating folder names as official IDs.
Share both manifests with `chunks.jsonl`, structured
measurement records, figure annotations/assets, and source/normalization
reports. Keep the manifest and QA report with each incremental batch.
