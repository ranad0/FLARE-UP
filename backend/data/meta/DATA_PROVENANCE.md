# NASA data coverage

Retrieved 15 November 2026 from the public NASA PSI service used by the official repository website. `raw/psi/search.json` preserves the combustion search response; the 26 complete investigation JSON payloads preserve project type, DOI, version, file inventory and research metadata. Public file downloads use the repository's download endpoint. Expiring signed URLs are neither persisted nor exposed.

## Judged corpus

19 **Microgravity Investigations** in **Combustion Science** are eligible: PSI-10, PSI-20, PSI-21, PSI-22, PSI-23, PSI-25, PSI-26, PSI-39, PSI-47, PSI-68, PSI-69, PSI-98, PSI-99, PSI-100, PSI-101, PSI-102, PSI-106, PSI-107 and PSI-159. No reduced-gravity-only investigation was returned by this search.

- 41 active science source files, 87,538,344 bytes: 40 existing downloads and one verified handoff PDF.
- 21 original experimental CSV tables; 2,001 nonblank source rows transcribed.
- 12,160 scalar numeric cells, each retaining the original field name, raw value, source row, conditions, DOI, URL and SHA-256.
- 113 active text chunks: investigation objectives/approaches/hypotheses with explicit evidence roles, and reviewed report passages.
- 2,001 original table-row text chunks in `review/table_rows_audit_only.jsonl`, excluded from descriptive retrieval. The structured path serves permitted numerical columns.
- 1,641 report/readme text chunks extracted into `review/report_chunks_pending_review.jsonl`. This archival extraction overlaps the reviewed excerpts; it is not 1,641 additional independent findings. Unreviewed passages remain excluded from judged retrieval.

These counts describe the downloaded subset, **not complete ingestion of every investigation**. Full raw collections include multi-terabyte video/image archives. Their filenames remain in the NASA metadata inventories, but those files are not represented as ingested observations.

## Evidence safeguards

An experimental table includes test conditions and campaign summaries as well as observations. A numeric cell is not automatically a measured outcome. Empty cells remain empty; ranges and semicolon-separated lists are preserved as text and never expanded into fabricated experiments.

2,737 scalar values have no explicit unit in their source header. Their units remain null. A further 258 FLEX cells carry the original header `Burning rate; mm`; this dimensional ambiguity is flagged and is **not** silently corrected to mm²/s. The app should always show quality flags and source headers when returning numbers.

The two PSI-159 CSVs were downloaded afresh and exactly match the supplied archive's SHA-256 hashes. PSI-10 and PSI-159 tables distinguish **normal versus inverse flame configuration**, not Earth versus microgravity. No Earth/microgravity comparison should be inferred from those labels.

PSI-99's experimental table mixes gravity regimes. Both `1-g` comparison columns are excluded from judged numeric values and conditions. The literal `?-g` labels in the downloaded CSV are ambiguous and are also excluded rather than silently repaired to microgravity. Three previously transcribed ground burn-length cells were removed from active observations. The complete original row remains in `source_row_values` strictly as provenance. No other table header explicitly labels a ground-gravity column.

## Reports and review

Selected passages were read in context before entering the judged corpus:

- PSI-159, `FinalRpt_ACME.CFI-G.pdf`, PDF page 23: only the first abstract reporting ISS spherical gas-fueled cool diffusion flames. The adjacent ground-based stagnation-flow abstract is excluded.
- PSI-39, `CFI Science Final Report.pdf`, PDF pages 3 (overview only), 5 and 6: ISS droplet-combustion background, operations and observations.
- PSI-102, `SAME_Final Science Report.pdf`, PDF pages 3–4: flight experiment abstract, with stated scope and comparison context preserved.
- PSI-25, `BASS-II Summary Report.pdf`, PDF pages 27 and 101: opposed-flow and concurrent-flow ISS abstracts, retaining fuel, oxygen and flow-regime scope.
- PSI-10, `FinalRpt_ACMEFlameDesign.pdf`, PDF page 25 and page 26 abstract: preliminary ISS results and model comparisons; page 27 follow-on section: experimental limitations.
- PSI-23, `s_Flame_final_report_20210729.pdf`, PDF pages 26–30: preliminary flight findings and interpretation; page 25: research goals and test matrix, labeled accordingly. Uncertainties and statements that further analysis is needed are preserved.
- PSI-101, `SAME-R_Final Report.pdf`, PDF page 3 flight-operations section and page 4 results overview: source descriptions of flight testing. The mixed flight/ground validation abstract is not used.
- PSI-107, `SPICE_FinalReport.pdf`, PDF pages 19–21 selected flight-method/results passages: coflow and soot observations. The draft's inconsistent total smoke-point counts and fuel rankings elsewhere are not ingested as findings.
- PSI-39, PDF pages 9–10: preliminary pressure, helium dilution and soot observations, with unresolved mechanisms retained.
- PSI-102, PDF page 25 results section and page 29 closing remarks: detector response and smoke-particle detection implications.

Other PDF text is extracted page by page into the review corpus. Figures, scanned pages and tables embedded as images are not OCR-validated or converted to numerical records. Sparse/image-only page numbers are listed per file. Two old `.doc` DAFT reports are downloaded but not parsed. Two BASS report downloads returned 404 even when retrying published version values; their failures remain in the ledger.

The 14 downloaded PSI PDFs contain 836 pages; 20 pages have sparse/image-only text and are not OCR-transcribed. Every investigation remains **partially ingested**: complete table transcription does not imply a complete investigation or complete unit review.

## Challenge supporting resources — separate collection

`supplemental/chunks.jsonl` contains **122 contextual chunks** from the following official NASA resources. They have `source_class=contextual_resource` and `judged_eligible=false`; they never enter the default judged investigation corpus. Historical accident cases, educational synthesis and technology-transfer stories are supporting context, not flight datasets.

| Resource | Status | Chunks |
| --- | --- | ---: |
| NASA Combustion Science webpage | Main article text ingested | 6 |
| NASA Researcher's Guide webpage | Main article text ingested | 1 |
| Linked NASA Combustion Science Researcher's Guide PDF | 56 pages; page text extracted, embedded numeric tables not validated | 91 |
| NASA Safety Center Apollo 1 | Visible page text ingested | 8 |
| NASA Safety Center Apollo 13 | Visible page text ingested; unrelated hidden Apollo 1 modal excluded | 8 |
| NASA Mir fire history | Main article text ingested | 4 |
| NASA Spinoff resource 9582 | Article text ingested | 1 |
| NASA Spinoff resource 9407 | Article text ingested | 1 |
| NASA Spinoff resource 9918 | Article text ingested | 2 |
| Challenge-linked YouTube W1oXykoz9zg | Metadata only; title not independently verified; no transcript | 0 |

`supplemental/resource_catalog.json` records exact URLs, titles, source filenames, hashes, retrieval date and status. Original HTML/PDF snapshots are in `supplemental/raw/`. Apollo 1 is explicitly a ground accident and is retained only in this contextual collection.

## Exclusions

PSI-115, PSI-117, PSI-142, PSI-60 and PSI-62 are Ground Investigations; PSI-181 is a Ground Investigation in Materials Science. PSI-108 is Fluid Physics and outside the selected combustion scope. Their metadata is retained for the audit, but none of their content enters judged text or structured retrieval. The old PSI-117 comparison fixture belongs only in `legacy/`.

## Rebuild

From the project root, after installing ingestion dependencies:

```text
python scripts/fetch_nasa.py
python scripts/fetch_files.py
python scripts/build_corpus.py
python scripts/fetch_supplemental.py
python scripts/verify_corpus.py
```

The first two commands require internet access. The supplemental fetcher needs internet only for missing snapshots; it reuses archived files. The builder and verifier work offline. Consult `ingestion_report.json`, `download_ledger.json` and `file_download_ledger.json` for complete per-file results. The downloader is intentionally restricted to public, visible reports/readmes and experimental tables below 60 MB each. Broader raw sensor/video ingestion requires additional format-specific parsing and gravity/conditions review.

## Handoff 3 update

Six exact Saffire source cells and one historical SAME design-objective paragraph were admitted through an explicit schema adapter. See [the full audit and migrations](../../../../docs/HANDOFF_3_REPORT.md). Other new extraction stays in isolated review storage.
