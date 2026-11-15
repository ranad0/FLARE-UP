# Seven-slide demo script

## 1 — FLARE UP: Flame in Freefall (15 seconds)
Show the homepage. Toggle Earth → Microgravity to demonstrate the coordinated flame, logo, glow and palette. Sweep the cursor near the flame. “FLARE UP turns NASA microgravity combustion research into evidence people can explore.”

## 2 — Why this matters (20 seconds)
Open NASA's Mir resource in Evidence. Explain the difficulty of fire detection, ventilation and suppression in spacecraft. Cite the linked NASA account; do not present historical incidents as controlled experiments.

## 3 — NASA data is the foundation (25 seconds)
Show the investigation catalog and provenance report: 19 microgravity investigations, 21 tables, 2,001 rows, 12,160 numeric fields and 123 selected chunks (62 reviewed report passages and 61 official metadata chunks). Explain that ground investigations are excluded from judged answers. Numeric fields are not separate experiments.

## 4 — One question, the right evidence path (40 seconds)
Ask “How does cabin airflow influence flame spread in spacecraft?” Show the text route and source locations. Then ask “Compare burn time for normal and inverse flames in PSI-159.” Show the structured route, actual units and row links. Run the hybrid example from README if time permits.

## 5 — Explore conditions (30 seconds)
Open Fire Lab, switch gravity and move airflow/oxygen controls. Request NASA evidence. Point out the explicit partial-match statement: the visual is illustrative, pressure-neighbor records are not exact predictions. This transparency is part of scientific validity.

## 6 — Explainable by design (25 seconds)
Show a source row and the context search. “We preserve values, units and provenance; unknown units stay unknown. NASA guides and safety history are searchable, separately from flight measurements.” Describe retrieval plus optional Groq synthesis accurately; only call a response generated when its status is groq-grounded.

## 7 — Impact and next step (15 seconds)
“An accessible research and education bridge, with a path to stronger scientific review and validated models.” Show the actual deployed URL after deployment, or the local demo today. Add team names and public project link before recording/submission.

High-level summary: FLARE UP is an interactive scientific evidence platform for exploring fire in microgravity. It combines NASA PSI flight investigations, structured numeric comparisons, traceable source retrieval and a responsive 3D exhibit. It helps users navigate complex research while making uncertainty and evidence boundaries visible.

AI usage: local statistical semantic/lexical retrieval and deterministic routing, followed by optional Groq openai/gpt-oss-20b synthesis with citation checks and a separate evidence review. Extractive answer assembly is retained when generation is unavailable. Optional MiniLM neural embeddings are preserved but not enabled in the tested default. Visual scenario effects are authored illustrations, not model predictions. Code/design assistance was used to build the platform; scientific records remain sourced from NASA.

References: the live catalog links each investigation; `backend/data/meta/DATA_PROVENANCE.md` documents files, hashes, exclusions and supplemental resources. Challenge: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=resources

Handoff 3 update: show `Compare burn time PSI-98` to demonstrate the newly admitted source cells.
The answer appears before expandable measurements and sources. Show “Why these results?” for
routing/filters and “Not Established” for limitations. If Groq is configured and `llm_status`
is `groq-grounded`, describe it as evidence-grounded synthesis using exact citations and a separate
entailment check. Otherwise explicitly describe the extractive fallback. No generated numbers.
