# FLARE UP
**Flame in Freefall — scientific intelligence for microgravity fire research.**

A search-first, bilingual web exhibit backed by NASA PSI evidence. Ask descriptive questions, retrieve source measurements, combine both paths, and explore an illustrative 3D Fire Lab.

## Live project
- Frontend: https://flare-up-ranad0.netlify.app/
- Full app / backend: https://flare-up-ranad0.onrender.com/
- Source: https://github.com/ranad0/FLARE-UP
- API documentation: https://flare-up-ranad0.onrender.com/docs

The free service sleeps after inactivity. Open it before the demo and allow a minute or more for startup. No paid inference or API keys are required.

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

## Visual modes
Use the Earth / Microgravity switch on Home. The flame, navbar mark, surrounding atmosphere, accents and pointer particles change together. Fire Lab shares that mode. Reduced-motion preferences disable decorative motion. See [visual behavior and verification](docs/VISUAL_STATE.md) and [judging criteria mapping](docs/JUDGING_MAP.md).

## What is preserved
The existing `text → retrieval`, `structured → numeric filters`, and `hybrid → both` architecture remains. `/ask` still returns `question`, `route`, `routing_reason`, `answer`, `llm_status`, `sources`, `structured_query`, `structured_results`, and `notes`. The original numeric parser and record layout were extended; source values are not replaced with generated numbers. Original backend modules are archived under `legacy/original_backend` for comparison.

## Data included
- 19 eligible NASA PSI **Microgravity Investigations**. No Reduced Gravity investigation was discovered in this combustion search; eligibility supports it when verified.
- 21 experimental CSV tables, 2,001 source rows, 12,154 scalar numeric records. Multiple records can come from one row; these are not 12,154 experiments. Some scalar fields are conditions or metadata rather than measured outcomes.
- 112 selected PSI passages, including objectives/hypotheses explicitly labelled as such and reviewed flight-report passages.
- Separate supporting collection: 122 chunks from challenge resources, including NASA's 56-page combustion guide. Ten resource entries: eight NASA webpages, one linked PDF, one video metadata-only.
- 40 PSI files downloaded (~87.3 MB), plus supporting resources. Large experiment video archives are inventoried, not downloaded. This is a broad, bounded snapshot, not all PSI data.

Ground investigations—including PSI-117—do not enter judged retrieval. The earlier `Dext_cool` model/experiment fixture remains in `legacy` and passes a parser regression. Its exclusion from current `/ask` results is intentional.

## Try the three routes
1. Text: `How does cabin airflow influence flame spread in spacecraft?`
2. Structured: `Compare burn time for normal and inverse flames in PSI-159`
3. Hybrid: `Compare burn time PSI-159 at 1.1 bar and explain the experiment`

Use **Evidence → NASA Space Apps resources** for guides, Apollo/Mir safety history and spinoff context. This collection is deliberately separate from `/ask` flight evidence.

## Retrieval and limits
The default is offline TF-IDF plus latent semantic analysis, followed by extractive evidence assembly. It is not a generative language model. Original local MiniLM embedding/vector modules are retained as an optional path; see `docs/ARCHITECTURE.md`. That optional neural setup has not been tested in this package. No paid inference API, Qdrant server, Ollama or Gemini runtime is needed.

Unknown units remain null. Dimensional concerns are flagged. Structured comparisons return source rows; they do not establish causal effects or safe operating limits. Fire Lab changes are illustrative, not CFD or numerical predictions. The pressure-neighbor examples explicitly do not match all scenario conditions. Arabic navigation and common topic expansion are supported; scientific source passages remain in their original language.

## Documentation
- [Architecture and schema compatibility](docs/ARCHITECTURE.md)
- [Dataset provenance, exclusions and review backlog](backend/data/meta/DATA_PROVENANCE.md)
- [Deployment](DEPLOYMENT.md)
- [Audit, changes and optional next work](docs/CHANGES.md)
- [Seven-slide demo script](docs/DEMO_SCRIPT.md)
- [Validation](docs/VALIDATION.md)

## Tests
```powershell
.\.venv\Scripts\python tests/test_engine.py
.\.venv\Scripts\python scripts/verify_corpus.py
.\.venv\Scripts\python tests/test_http.py http://127.0.0.1:8010
```
The HTTP test needs the server running. Ingestion scripts and optional model indexing have separate requirements; see architecture documentation.

This independent Space Apps project is not a NASA operational fire-safety system or a NASA-endorsed product. Sources retain their original attribution; see `NOTICE.md`.
