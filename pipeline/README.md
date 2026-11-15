# Authoritative data-team ingestion subsystem

The source in this directory is the teammate pipeline from handoff 3, compared against the
previous supplied pipeline before integration. It remains separate from the web application.
Eighteen Python files were unchanged, seven updated, and four new. The pipeline data contract
itself is unchanged (2.0.0). See the file hashes in `../data_handoffs/handoff_3/audit_report.json`.

Preserved sequence: raw NASA files → source registry/manifest → format-specific handlers →
conservative normalization → scalar measurements and separate text chunks → QA/manifests →
versioned outputs → explicit application compatibility adapter.

Accepted source improvements include explicit CSV encoding fallback, atomic output writes,
additional identifier exclusions, OOXML paragraph/slide/image locators, workbook discovery
chunks, scoped finalization, and supporting safety-case processing. No pipeline script was
allowed to overwrite the current application corpus. No cloud upload credentials or browser
profiles are included. Optional browser/download/upload helpers are retained as source only.

Use a separate Python environment for the original ingestion dependencies in `requirements.txt`.
The app runtime does not need Playwright, OOXML extraction, or PDF image extraction.
Place originals in `pipeline/data/raw/<investigation>` (or set `FLARE_UP_RAW_DIR`), register
their NASA source URLs, then use `src/process_manual_investigation.py`,
`src/normalize_experimental_csv.py`, `src/chunking.py`, and `src/finalize_batch.py` with their
documented investigation filters. Review output before adding an explicit admission decision.
`validated_structure` is structural QA, not scientific validation. Filename-indicated series
types require independent source verification. Unknown units remain null. Dataset-index and
visual records cannot become measurement evidence merely by being finalized.

For the checked-in app, rebuild with `python scripts/build_corpus.py` from the app root. It
rebuilds the existing curated corpus and invokes the handoff adapter, which checks exact source
hashes, CSV cells, schema versions, eligibility, and the explicit approved-record allowlist.
Repeated rebuilds do not duplicate records. The adapter preserves each original 2.0.0 numeric
record inside migration provenance; it never edits the original handoff JSONL.
