# PSI browser acquisition

## What is implemented

`src/download_psi_browser.py` uses Playwright-managed Chromium with a dedicated persistent profile under `data/tmp/psi_chromium_profile/<PSI-ID>`. It does not launch the installed Chrome channel or inspect the user's personal browser profile, cookies, or passwords.

The script opens a public PSI investigation page, opens its “Data files and documents” section, observes NASA file routes, selects at most one CSV (or one explicitly named file), and waits for a browser download event around the UI click. This supports PSI controls that start downloads from JavaScript. It never solves CAPTCHAs or bypasses access restrictions.

The one-file pilot writes to `data/tmp/psi_downloads/<PSI-ID>/`, refuses to overwrite, retries up to three times, calculates SHA-256, and appends source URL, investigation URL, filename, byte size, HTTP status when observable, and result status to `data/tmp/psi_download_manifest.jsonl`. It writes a detailed run report under `reports/` and logs to `reports/psi_browser_download.log`. It does not remove downloaded files or the isolated profile.

## Dependencies and permissions

- The project already lists the Python package `playwright` in `requirements.txt`. The Playwright-managed Chromium browser binary is a separate one-time download; it is not the user's installed Chrome.
- The downloader itself uses only the Python standard library and Playwright. It does not need Google packages.
- Downloading requires outbound network access to the public PSI site and write permission inside this project's `data/tmp/` and `reports/` folders.
- The optional Drive uploader uses `requirements-gdrive.txt`, the Google Drive API, and OAuth scope `drive.file`. It requires a Google OAuth Desktop client JSON file created by the user in Google Cloud. The program never requests a Google password; it opens an OAuth URL for the user to authorize. The OAuth token is stored under the user's Windows AppData, outside the project.

## Run one PSI-10 pilot

From the project root, first install only the browser binary if it is not already installed:

```powershell
$projectPath = (Resolve-Path .).Path
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectPath 'data\tmp\playwright-browsers'
& 'C:\Users\USER\Desktop\flare-up\.venv\Scripts\python.exe' -m playwright install chromium
```

Then run one file only:

```powershell
& 'C:\Users\USER\Desktop\flare-up\.venv\Scripts\python.exe' .\src\download_psi_browser.py PSI-10
```

To select a specific visible file after confirming its exact name on the page:

```powershell
& 'C:\Users\USER\Desktop\flare-up\.venv\Scripts\python.exe' .\src\download_psi_browser.py PSI-10 --file 'exact filename.csv'
```

The first run defaults to the first CSV discovered from live page requests. A successful result reports the exact local path, byte count, SHA-256, and a manifest record. Review and open the file before passing it to handlers or RAG. The old `download_psi_pilot.py` used a direct HTTP request and rejected NASA's HTML response; use `download_psi_browser.py` for the UI-driven test.

## Optional Google Drive upload

Review `requirements-gdrive.txt` before installing its two OAuth/API packages. Save an OAuth Desktop client file as `config/oauth/google_oauth_client.json`; `.gitignore` excludes that file and the OAuth directory. Run:

```powershell
& 'C:\Users\USER\Desktop\flare-up\.venv\Scripts\python.exe' -m pip install -r .\requirements-gdrive.txt
& 'C:\Users\USER\Desktop\flare-up\.venv\Scripts\python.exe' .\src\gdrive_upload.py '.\data\tmp\psi_downloads\PSI-10\exact filename.csv'
```

The uploader verifies the remote byte size and MD5 before reporting success. It never deletes the local file by default. If local removal is explicitly requested with `--remove-local-after-verified`, the user must type `REMOVE LOCAL FILE` after verification; otherwise the local file remains.

Do not run download-all across investigations until file inventory, sizes, checksums, and handler outputs have been validated.
