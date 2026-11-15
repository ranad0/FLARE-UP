# Handoff 3 audit and selective merge

The GitHub application at `4042f2a17bf3558b6d3ddba3c6d98d6858c585cb` was the baseline.
The ZIP was audited separately before changing production data. This update does not replace
the frontend, backend, router, Fire Lab, or deployment configuration.

## Disposition

| Category | Finding and decision |
|---|---|
| NEW | Six PSI-98 scalar fields; six PSI-101 engineering PDFs; supporting safety-case collection; additional BASS documents. No new investigation admitted. |
| UPDATED | Seven team pipeline Python files; explicit CSV encoding, OOXML support, identifier exclusions, scoped finalization. Four new helper modules. |
| UNCHANGED | Eighteen pipeline Python files, including the 2.0.0 data contract. Existing 12,154 scientific values/units preserved. |
| DUPLICATE | 5,607 numeric records match existing source-hash/row/column keys and values/units; ten raw files match existing bytes. Not appended. |
| INCOMPATIBLE | Unversioned PSI-10 processed output lacks a matching source in the handoff raw collection; no automatic import. 2.0.0 cannot be silently mixed into app 3.0. |
| NEEDS REVIEW | 180 automatic PSI-101 chunks; 864 figure captions; additional BASS originals; safety-case extraction and missing primary files. |
| EXCLUDED | PSI-117 ground data, legacy visual annotations, STDCE outside combustion, browser binaries/profiles/cache, and temporary files. |

## Actually integrated

- PSI-98: `Ignition Power (W)`, `Ignition Time (s)`, `Burn Time (s)` in source rows 2 and 3.
  Six exact cells; header units W/s/s. Values are unchanged, including `value_raw`, conditions,
  source column and row, quality flags, and original provenance. Source CSV bytes already existed.
- PSI-101: one reviewed opening paragraph of section 2.3 in *SAME Baseline Concept Description*,
  PDF page 7 / printed page 3. Explicitly labelled historical design objective, not reflight results.
  No numerical measurements were extracted from the PDF or figures.
- Original team pipeline source and immutable handoff JSONL/QA snapshots in isolated directories.
  Other staged material is pending; it is not read by `/ask` or Fire Lab.

NASA's live investigation API confirmed both selected IDs as Combustion Science / Microgravity
Investigations. Verification snapshots retain titles, DOI and API URLs. Existing DOI metadata is
preserved; null handoff DOI is supplemented from official metadata with its basis recorded.

## Compatibility and rebuild

`handoff-2.0.0-to-app-3.0-v1` is an explicit allowlisted adapter. It verifies source hashes and exact
CSV cells, retains complete original records inside migration provenance, adds official eligibility
and source-path metadata, and rejects conflicting duplicates. The original source has
`series_type_basis=filename_indicated`; the adapter records independent confirmation against the
already integrated NASA experimental-table hash. It does not infer gravity from filenames.
Unknown units in the rest of the corpus remain null. Normal/inverse flame distinctions remain intact.

`scripts/build_corpus.py` invokes this adapter after the existing base build. Local TF-IDF/LSA is
rebuilt from the new corpus on fresh process startup; structured records are reloaded on startup.
Optional MiniLM indexes require `scripts/index_minilm.py` and remain hash-checked; a stale index
falls back to local retrieval rather than silently using old data.

## New totals

| Collection | Total |
|---|---:|
| Eligible judged investigations | 19, all Microgravity; zero new IDs |
| Active PSI source files | 41: 40 existing downloads + 1 verified handoff source |
| Judged text chunks | 113: 61 official metadata passages + 52 reviewed PDF passages |
| Structured source rows | 2,001 across 21 existing CSV tables |
| Scalar records | 12,160 (six added; not separate experiments) |
| Active supporting resources | 10 entries / 122 chunks, unchanged |
| Existing report extraction pending review | 1,641 chunks, unchanged |
| Existing table-row audit text | 2,001 rows, excluded from semantic retrieval |

Additional isolated contextual handoff: 5 safety cases, 1,662 chunks (42 curated summaries and
1,620 extracted excerpts), 32 claims, 16 historical/hardware values, 20 source catalog entries.
These do not increase active supporting or judged totals. The handoff QA flags ten missing local
source files, one catalog entry without a URL, and one exact duplicate preserved for provenance.

## Answer-first search

Retrieval routes and existing response fields remain; additive `synthesis` and `extractive_evidence`
fields support a concise answer above expandable evidence. Optional Groq `openai/gpt-oss-20b`
uses only the retrieved text bundle. It selects source IDs; the server resolves
the exact supporting text, rejects numerical prose, and requests a separate entailment check.
Numeric summaries are formatted from structured records only. These checks reduce errors but are
not proof of scientific validity. Full source passages remain available. Missing key, timeout,
invalid output or failed grounding checks produce an explicit extractive fallback.

No direct OpenAI API is used. Groq is configured on the live backend; provider failures and rejected
drafts still use the extractive fallback. See the architecture document for the current synthesis contract.
Model output is separated into Reported by Sources, Interpretation, Not Established, and Sources.
No model confidence percentages or physical predictions are introduced.

## Validation

- All six handoff batch manifests matched their listed files in the extracted ZIP.
- All active source hashes, exact CSV `value_raw` cells, IDs and eligibility checks passed.
- Numeric duplicate keys and migration equality checks passed; no PSI-117 or pending collection
  entered judged retrieval; supporting resources remain separate.
- Backend unit tests cover text/structured/hybrid routes, new Saffire fields and SAME objective,
  unknown units, Fire Lab, missing-key behavior, invalid quotes/citations, rejected entailment,
  invented numbers and provider timeout.
- Frontend typecheck/build and real local HTTP endpoint checks passed.
- Remaining limits: no complete investigation ingestion claim; no complete NASA PSI ingestion;
  no figure digitization; no unreviewed safety source promotion; live Groq requires a server key.

Machine-readable file/record details: `data_handoffs/handoff_3/audit_report.json`,
`review_decisions.json`, and `backend/data/meta/ingestion_report.json`.
