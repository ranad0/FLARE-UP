# Architecture and data compatibility

## Request path
React/TypeScript → FastAPI `/ask` → deterministic router → text retrieval / structured filtering / both → evidence bundle → optional grounded Groq synthesis / extractive fallback → answer + source records.

`app/router.py` retains the original decision fields: `route`, `reason`, `numeric_term_hits`, `has_number`, `has_unit`, `has_measurement_target`, `asks_interpretation`. Target-word matching is tightened so general questions about an experiment or airflow do not automatically become numeric requests.

`app/structured_data.py` extends the original implementation: canonical PSI IDs, more source-specific quantity aliases, pressure normalization, fuel aliases, unknown-unit handling and balanced normal/inverse result selection. No language model parses or invents numeric answers. Pressure comparisons use ±0.015 bar; source pressure units are preserved, and conversion supports filtering only. Rows with multi-valued/ambiguous pressure are not silently expanded into new experiments.

`app/rag.py`, `app/retrieval.py`, and `app/catalog.py` remain public entry modules. The integrated retrieval and evidence assembly implementation is in `app/evidence.py`. Original code is kept in `legacy/original_backend` (reference only; not imported). The old paid-provider synthesis adapter is archived rather than required.

## Collections
| Location | Purpose | Default /ask |
|---|---|---|
| `backend/data/chunks.jsonl` | Selected eligible PSI text passages | Yes |
| `backend/data/structured/nasa_observations.jsonl` | Original numeric fields with provenance | Yes, structured/hybrid |
| `backend/data/raw` | Original NASA metadata, tables, reports and manifests | Through reviewed records only |
| `backend/data/review` | Audit-only extraction and pending review | No |
| `backend/data/supplemental` | Challenge guides, safety history and context | No; explicit resources search |
| `legacy` | Earlier code and PSI-117 Dext fixture | No |

A flight investigation label alone is insufficient to trust every report paragraph or table column: reviewed flight passages are selected, and explicit ground/ambiguous gravity columns are removed from active quantities/conditions. Complete original rows are retained for audit and can contain excluded columns; these are not active observations.

## Additive schema
Text records preserve `chunk_id`, `investigation_id`, `investigation_title`, `content_type`, `text`, `embedding_text`, `source_file`, `source_location`, `citation_url`, `doi`. Additional provenance includes `project_type`, source hash and evidence role where applicable.

Numeric records preserve `record_type`, `investigation_id`, `quantity_name`, `value`, `unit`, `conditions`, `source_file`, `source_location`, `citation_url`, `doi`; schema 3 adds canonical investigation metadata, source SHA-256 and source row values. Raw column titles remain available. A null unit is a real uncertainty, not an invitation to infer one. Source quality flags propagate to returned records.

The legacy Dext fixture uses the original schema and parser test. Its original PSI label is now resolved: NASA identifies PSI-117 as Ground Investigation. It is kept for compatibility/history, not recategorized as microgravity.

## Default retrieval
TF-IDF word/bigram vectors plus local truncated SVD (up to 96 latent components), fused lexical/latent cosine scores with relevance gates. This is a lightweight local semantic approximation, not MiniLM or LLM synthesis. Results are extractive and source-labelled. Hybrid answers join evidence types without inventing a causal explanation. English is the primary scientific retrieval language; a small Arabic topic glossary helps common queries.

## Optional original MiniLM path
`embedder.py` and `vector_store.py` preserve the supplied local embedding / JSON cosine-index approach. To opt in from project root:

```powershell
.\.venv\Scripts\python -m pip install -r backend/requirements-semantic.txt
.\.venv\Scripts\python scripts/index_minilm.py
$env:RETRIEVAL_MODE = 'minilm'
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010
```

Model: `sentence-transformers/all-MiniLM-L6-v2`; initial model download needs internet, then inference is local. This optional path is **not validated in this build**. It fuses vector/lexical ranks and checks the corpus SHA-256 before using the index. Missing/stale dependencies or index cause an explicit local fallback warning on returned passages. Rebuild after data changes. Do not describe the default as running MiniLM.

## Ingestion maintenance
Install `scripts/requirements-ingestion.txt` in an isolated environment. `fetch_nasa.py`, `fetch_files.py`, `build_corpus.py`, `fetch_supplemental.py`, `verify_corpus.py` hold the reproducible selection/extraction steps. Read the scripts before refreshing: NASA contents and counts may change. Keep raw files and ledgers; review new report passages before adding them to the allowed passage selection. Restart the API after any rebuild (indexes and records are cached).

## Other endpoints
`GET /health`, `/stats`, `/investigations`, `/provenance`, `/resources`; `POST /route`, `/search`, `/structured-search`, `/resources/search`, `/scenario/analyze`. `/docs` documents schemas.

Scenario analysis is explicit about evidence gaps: only gaseous-fuel microgravity conditions are linked to nearby CFI-G pressure records, and fuel composition, oxygen, geometry and flow are not claimed to match. Earth/solid scenarios return context without numeric matches. Visuals have no calibrated physical solver.

## Handoff compatibility and optional synthesis

The teammate `pipeline/` owns ingestion. `scripts/merge_handoff.py` explicitly adapts approved
2.0.0 records into application 3.0, preserving complete originals and checking source cells.
`data_handoffs/handoff_3` is a review snapshot, never a retrieval input directory.
See [the handoff report](HANDOFF_3_REPORT.md) for exact boundaries.

`app/synthesis.py` adds Groq `openai/gpt-oss-20b` after retrieval. It checks exact quotes/source IDs,
rejects numerical prose, and runs a separate entailment review. The model cannot supply numeric
summary values: the server renders those from retrieved records. Automated entailment is a
safeguard, not scientific certification. Two calls can add latency; each has an 18-second timeout.
No key or failed checks → extractive fallback. Existing `/ask` fields remain; additive fields
`synthesis` and `extractive_evidence` expose the answer sections and original retrieval assembly.
