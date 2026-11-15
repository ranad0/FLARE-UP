# Judging criteria and demo evidence

| Criterion | Demonstrate | Boundary to state clearly |
|---|---|---|
| Impact | Accessible search into spacecraft combustion and safety research | Research/education tool, not operational safety advice |
| Creativity | Coordinated Earth/microgravity atmosphere, velocity-responsive flame, 3D exhibit | Authored qualitative visualization, not CFD |
| Validity | Values/units/conditions and source locations; unknown-unit and Not Established behavior | No inferred units or manufactured confidence |
| Relevance / NASA data | Verified microgravity PSI corpus and separate challenge resource search | Ground, pending-review and contextual resources are not promoted into judged measurements |
| Presentation | Minimal search-first homepage, two modes, three routed example questions, sources panel | Show a source result after the visual moment; NASA evidence stays central |

Suggested opening: switch Earth → Microgravity, sweep the cursor near the flame, then immediately ask the BASS airflow question. Show the source location and evidence role before opening the lab. Use docs/DEMO_SCRIPT.md for the seven-slide sequence and README.md for local setup.

## Official challenge alignment review — 2026-11-15
Reviewed https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details in Chrome.

The challenge asks for an interactive web dashboard that helps users summarize, rank and interpret microgravity combustion investigations for crew-environment fire safety. Its suggested features include identifying relevant investigations, extracting data for modeling, and highlighting prevention/detection/suppression research. Suggested comparison attributes include fuel, sample geometry, oxygen, airflow, measurement methods, and common/different test conditions.

- **Find/rank:** live question routing and query-relevance-ranked NASA evidence. Ranking is relevance, not scientific confidence or safety ranking.
- **Understand:** the response now separates measurements from readable source-excerpt previews. Full quotations, evidence roles and citations remain accessible. The answer-first layer optionally uses Groq grounded synthesis with quote checks and a separate entailment review; without a key it remains extractive. Automated checks do not certify scientific validity.
- **Compare:** values and units remain in a distinct table; each row expands source location and original conditions. Different conditions are explicitly cautioned. Matched-condition statistical comparisons remain future work.
- **Interpret responsibly:** Fire Lab distinguishes reported source records, interpretation and unknown outcomes. It does not predict flammability from arbitrary controls.
- **Prevention/detection/suppression:** use BASS/Saffire, SAME and FLEX evidence queries respectively; supporting resources remain in their separate collection.
- **Beyond a basic dashboard:** coordinated gravity atmosphere, interactive disturbance, bilingual navigation, source hashes, strict ground-data exclusion, and real public API deployment improve presentation and auditability.

The challenge states that partial-gravity combustion data is currently unavailable in PSI. Do not claim lunar or Martian surface measurements or treat Earth/microgravity visuals as a validated interpolation. Rocket/propellant safety is outside the stated PSI research scope. The current offline retrieval is not a demonstrated superintelligent model; disclose that limitation. Exceeding judges' expectations is an aim, not a guaranteed outcome.
