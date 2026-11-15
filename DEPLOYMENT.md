# Deployment

## Recommended: one service
Serve the built frontend from FastAPI on the same origin. This avoids separate API URLs and CORS configuration. The included Dockerfile builds the frontend and packages the Python API. Any host supporting Docker web services can run it; Render is a straightforward option. Hosting quotas, availability and costs should be checked in your account; no paid inference API is required.

1. Create a GitHub repository from the contents of `FLARE_UP` (the project root, not its parent audit folder).
2. Include source, package-lock, data, docs and Dockerfile. `.gitignore` excludes local environments, caches, `.env`, model storage, node_modules and built frontend. The downloadable ZIP separately includes the built frontend for local demos.
3. In Render, create a Web Service from the repository and select Docker. Use the root Dockerfile and health check `/health`. No build/start override is needed.
4. Set `RETRIEVAL_MODE=local`. The Docker startup uses the host's `PORT` (default 8010).
5. Visit `/health`, `/docs`, then run the three README demo questions on the public site.

Published and verified on Render on 2026-11-15: https://flare-up-ranad0.onrender.com/ . GitHub: https://github.com/ranad0/FLARE-UP . The free Docker service uses health check `/health` and `OPENBLAS_NUM_THREADS=1`. Text, structured, hybrid, scenario and supporting-resource HTTP checks passed against this public origin. The free instance sleeps when idle and Render reports wake-up delays of 50 seconds or more. Frontend requests allow up to 120 seconds; open the service before presenting. Official reference: https://render.com/docs/deploy-fastapi . The Docker route builds Node assets before starting the same FastAPI server described there.

Local container commands:
```sh
docker build -t flare-up .
docker run --rm -p 8010:8010 flare-up
```
Docker was built successfully by Render; it was not built locally.

## Published split deployment

Netlify frontend: https://flare-up-ranad0.netlify.app/ . Render API and full-app fallback: https://flare-up-ranad0.onrender.com/ . The static upload uses `config.js` with that API origin; Render `ALLOWED_ORIGINS=https://flare-up-ranad0.netlify.app`. No wildcard origins or credentials are needed.

Netlify was published by ZIP upload, not automatic Git integration. To update it, build `frontend/dist`, copy its contents to a staging directory, set staging `config.js` to `window.FLARE_CONFIG = {apiBaseUrl: "https://flare-up-ranad0.onrender.com"};`, then upload that directory or its ZIP in this project's Deploys page. Keep the local build config empty for same-origin localhost. The included `netlify.toml` also prepares a future Git-connected build. Render was connected through the public repository URL; use **Manual Deploy - Deploy latest commit** after pushing changes.

## Alternative split setup
- Frontend: Netlify, base directory `frontend`, build `npm ci && npm run build`, publish `dist`.
- Backend: a Python/Docker web service. Python build: `pip install -r backend/requirements.txt`; start: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`.
- Set frontend **build-time** `VITE_API_BASE_URL=https://YOUR-BACKEND-HOST` (no trailing slash). It is a public URL, never a secret. Rebuild after changing it.
- Alternatively set `apiBaseUrl` in `frontend/public/config.js` before building, or the deployed `config.js` for a prebuilt static upload. Runtime config takes precedence.
- Set backend `ALLOWED_ORIGINS=https://YOUR-FRONTEND-HOST`, comma-separated for multiple explicit origins. Use HTTPS for both. CORS is not authentication.
- Do not put `/api` at the end of the production URL; `/api` is only the local Vite proxy prefix.
- Official Vite/Netlify settings: https://docs.netlify.com/build/frameworks/framework-setup-guides/vite/ .

## Environment variables
| Variable | Location | Default / role |
|---|---|---|
| `RETRIEVAL_MODE` | Backend | `local`; optional `minilm` requires installation/index |
| `ALLOWED_ORIGINS` | Backend | Local 5173/8010 origins; explicit production frontend if split |
| `TOP_K` | Backend | 7 passages |
| `CHUNKS_PATH` | Backend | Bundled eligible chunks |
| `STRUCTURED_DIR` | Backend | Bundled structured records |
| `HF_EMBED_MODEL` | Optional backend | all-MiniLM-L6-v2 |
| `LOCAL_VECTOR_INDEX` | Optional backend | backend/storage/vector_index.json |
| `VITE_API_BASE_URL` | Frontend build | Empty → same origin in production |
| `PORT` | Container host | 8010 |

No API keys are needed. For a public production service beyond judging, configure host request limits and monitoring. The prototype has no accounts, persistence of questions, or collaboration features. Keep local offline demo dependencies installed before the event and test on the actual presentation laptop.
