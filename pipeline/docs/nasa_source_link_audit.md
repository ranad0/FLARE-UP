# NASA source link audit

Checked 14 November 2026 for Flare Up's configured source list.

## PSI investigation pages

All 24 supplied URLs use the official NASA PSI investigation route:

`https://psi.nasa.gov/physci/repo/data/investigations/{PSI-ID}`

The read-only web viewer returned NASA PSI HTML for 22 of the supplied page URLs, but did not expose readable page contents for those URLs. It could not access PSI-106 and PSI-23, so those two are not independently verified by this check. Search indexing exposed readable official investigation content for PSI-62, PSI-101, PSI-107, and PSI-98, confirming that this route is used for investigation metadata and file listings. PSI-107's page reports a 6.47 GB file collection, so downloading every linked folder at once is not suitable for the first ingest.

The official NASA PSI guide says each investigation can have folders for raw/analyzed data, reports, and supporting documents, and that users select files or a folder in the repository's file browser to download them. The read-only viewer cannot confirm the underlying direct file URLs for each of the 24 pages. Therefore, the manifest points to investigation landing pages; it does not claim those pages are direct downloadable source files. The runtime source-ingestion report must be reviewed for each page. A status of `metadata_only_file_links_not_exposed` or `requires_dynamic_browser_adapter` means the file-browser/API path remains unresolved for that investigation.

## General references

- NASA Combustion Science page: the page opens and exposes readable NASA HTML.
- NASA Researcher's Guide to Combustion Science: the page opens and exposes NASA HTML.
- YouTube ScienceCasts URL: the user-provided URL follows the normal YouTube video URL format, but the read-only viewer could not fetch the video or provide captions. It is configured as a video source awaiting an authorized direct VTT/SRT caption URL.

## Current code capability

The new web-source path parses static NASA HTML, stores extracted text with the source URL, and catalogs direct links to common scientific and media file extensions. It does not execute JavaScript, click PSI's file-browser controls, or call an undocumented endpoint. Direct file sources already support PDF, CSV, XLSX, TXT, JSON/JSONL, VTT/SRT, and ZIP. DOC/DOCX, PPT/PPTX, old XLS, images, and video can appear in the link catalog but still need dedicated content handlers before they can become RAG records.

This audit deliberately separates verified site/page access from actual file acquisition. The first successful pipeline run will be the definitive operational check for the user's machine/network and the PSI page's current HTML.

