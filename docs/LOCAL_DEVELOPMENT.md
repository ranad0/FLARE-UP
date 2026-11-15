# Local development

## Run the included build (Windows)

Python 3.11+ is required. Open PowerShell in this extracted `FLARE_UP` folder:

```powershell

py -3.11 -m venv .venv

.\.venv\Scripts\python -m pip install -r backend/requirements.txt

.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010

```

Open http://127.0.0.1:8010/ . API documentation: http://127.0.0.1:8010/docs . Stop with Ctrl+C. If `py -3.11` is unavailable, use your installed Python 3.11+ executable. The ZIP includes `frontend/dist`, so Node is not required to run the prepared demo. First dependency installation needs internet; default retrieval then runs locally without API keys.

On macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r backend/requirements.txt`, and `.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010`.

## Develop the frontend

Use Node 22.12+ and a second terminal:

```powershell

cd frontend

npm ci

npm run dev

```

Vite runs at http://127.0.0.1:5173 and proxies `/api` to the backend on 8010. After editing, run `npm run typecheck` then `npm run build`; the Python server serves the new build at 8010.


## Validation and data maintenance

Run `python -m unittest discover -s tests -p "test_*.py"` and `python scripts/verify_corpus.py` from the project root. With the API running, run `python tests/test_http.py http://127.0.0.1:8010`.

The teammate ingestion subsystem is in `pipeline/`. Approved handoff records pass through the explicit compatibility adapter in `scripts/merge_handoff.py`; `python scripts/build_corpus.py` rebuilds the curated corpus and applies that adapter. Restart the API after a rebuild. Pending material in `data_handoffs/` is not searched.

Set server-side `GROQ_API_KEY` to enable Groq `openai/gpt-oss-20b` synthesis. The key is optional for retrieval and must never appear in frontend code. See [deployment](../DEPLOYMENT.md), [architecture](ARCHITECTURE.md), and [data audit](HANDOFF_3_REPORT.md).
