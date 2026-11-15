# Source URL ingestion

Use `config/source_links.json` as the active manifest. The example file has the same supported schema. Keep every `source_key` unique and put each investigation in its own `source_group`.

## Source types

- `file`: a direct HTTPS URL to PDF, CSV, XLSX, TXT, JSON, JSONL, VTT, SRT, or ZIP. It must return the file itself, not an HTML page.
- `psi_investigation`: an official NASA PSI investigation landing page. The handler fetches the page, saves readable server-rendered text under `data/raw`, and reports direct downloadable file links visible in the HTML, including unsupported file formats. It does not download an entire investigation or recursively fetch file links.
- `webpage`: readable NASA HTML reference pages. The handler extracts visible text and catalogs supported file links.
- `youtube`: the video link is recorded, but captions require an authorized direct VTT/SRT `transcript_url`. The video is not downloaded and captions are not scraped.

PSI investigations can contain large, heterogeneous folders. NASA's PSI guide describes selecting a file or entire folder for download, and warns that files over 1 GB need a separate workflow. Review `reports/source_ingestion_report.json` before adding discovered URLs as `source_type: file` entries. This keeps the initial pipeline bounded and lets the team choose relevant files. The ingestion report records a page's discovered direct file links when those links are present in the HTML.

PSI uses a client-rendered file browser on some pages. If the report says `requires_dynamic_browser_adapter`, the landing page returned no usable server-rendered text. This is a real adapter limitation, not evidence that the investigation has no files. Do not treat a landing-page link as a direct file URL. At that point the dynamic PSI file-browser/API endpoint must be identified and supported before claiming that its folder contents were acquired.

To inspect the rendered PSI interface safely before building its downloader, see [the PSI browser adapter pilot](psi_browser_adapter.md). Its Playwright probe does not download or select files.

The current file-processing handlers support PDF, CSV, XLSX, TXT, JSON/JSONL, VTT/SRT, and ZIP (with supported members extracted from ZIP). The catalog may also list DOC/DOCX, PPT/PPTX, legacy XLS, images, and video, but these need their own processing handlers before their contents can be included in the RAG batch. A file being listed or downloaded is not the same as its contents being parsed.

Investigation IDs in the manifest point to their official NASA PSI pages. Ingestion only promotes an ID to `verified` when readable page text contains that same ID and the evidence URL is present; a missing or generic page remains `unverified`. Parsed content, filenames, and measurements still need scientific review; successful ingestion alone does not validate a claim, unit, DOI, or value.

## Run the source step

From the project root:

```powershell
python .\src\ingest_sources.py
```

Inspect each status and `file_links` in `reports/source_ingestion_report.json`. If an entry fails because of a temporary NASA/network issue, retry it separately by keeping a smaller manifest rather than repeatedly fetching every source.

For each selected discovered direct file URL, add a separate `source_type: file` entry with its own `source_key`, `source_group`, `investigation_id`, `investigation_id_evidence_url`, and `citation_url`. Keep ZIPs intact; the pipeline extracts their members safely and retains the original archive.

Then, from the project root, process data in order:

```powershell
python .\src\inventory.py
python .\src\main.py
python .\src\normalize_dext.py
python .\src\normalize_burning_history.py
python .\src\chunking.py
python .\src\finalize_batch.py
```

Review the ingestion and QA reports before handing off a batch. The finalizer writes schema-versioned chunks, structured records, figure-asset records, provenance, and `reports/batch_manifest.json`. A successful parse does not mean that a scientific claim, unit, DOI, or investigation identifier has been independently verified.

