# Text chunks for RAG

## Run the chunking step

From the project folder, run:

```powershell
python src/chunking.py
python src/finalize_batch.py
```

The first version uses a 250 word target with 40 words of overlap. You can tune it for a trial run:

```powershell
python src/chunking.py --target-words 200 --overlap-words 30
```

The script reads the handler JSONL files under `data/processed/` and writes:

- `data/processed/chunks.jsonl`
- `reports/chunking_report.json`
- `reports/qa_report.json` and `reports/batch_manifest.json` (from the finalizer)

## What becomes a text chunk

- Each PDF page with extractable text is chunked separately. This keeps the page number and any extracted figure references attached to the text.
- TXT documents are split into overlapping word windows.
- Rows from an Excel file named as a ReadMe or data index become short searchable descriptions, with the original column labels included.

The PDF handler extracts images, but this step does not generate AI descriptions for them. The finalizer emits a `figure_asset` record per extracted image, linked to its document and page; captions stay `null` with `caption_status: needs_review` unless reviewed. A figure description is not digitized measurement data.

## What stays structured

Numeric CSV and Excel rows are not turned into prose chunks. Their original columns, values, row numbers and source paths remain in the handler JSONL output. A later structured-query step should load those records into SQLite or an equivalent store. This protects units and table shape and lets the agent retrieve exact values.

## Chunk fields

Each finalized JSONL record uses `schema_version: 2.0.0` and has a stable `chunk_id`, `document_id`, source file/path, `source_location`, `text`, `embedding_text`, and a nested `provenance` chain. Embed `embedding_text` and retain metadata for filtering/citations. A folder label such as `PSI-117` is carried as `investigation_label` with `investigation_id_status: unverified`; it is not exposed as an official `investigation_id` without evidence.

The chunk sizes use word counts as a temporary approximation. Once the team selects an embedding model, use its tokenizer to tune the target size. The current PSI-117 PDF is a slide presentation, so page-level chunks fit this source. Longer papers may need section-aware chunking that carries headings across pages.

## Responsible handoff

Treat `PSI-117` as an unverified workspace label, not an official investigation ID. Keep each chunk tied to its exact source location. Before importing, require a valid v2.0.0 batch manifest and QA report, then agree on field names, ID stability, embedding text, source display, and refresh behavior.
