# Validation and scientific limits

We validate retrieval, provenance, API behavior and presentation separately. Automated checks do not constitute scientific certification.

## Current checks
- 41 offline unit tests passed, covering routing, source traceability, ground-data exclusion, unknown units, schema compatibility, synthesis citation checks and fallback behavior.
- Local HTTP tests passed for text, structured and hybrid queries, English/Arabic retrieval, all four Fire Lab sample categories, supporting-resource separation and request validation.
- Corpus verification passed for 123 text chunks and 12,160 scalar records. Original source values and hashes remain traceable. The 122 supporting chunks are separate.
- Frontend type checking and production build passed. Browser checks covered language selection, gravity modes, search, source links and Fire Lab evidence.
- Canvas checks cover mode transitions, cursor recovery, reduced-motion preferences and rendering cleanup.

## Interpretation and generation
We use optional Groq synthesis only after retrieval. Generated qualitative claims must retain source support and pass validation. Numeric values come from structured records. If generation is unavailable or fails a check, we display original evidence and explicitly label the fallback. Offline mocked-provider tests do not establish live-provider availability or scientific correctness.

## Fire Lab
We illustrate buoyancy and ventilation qualitatively. Smoke visibility is intentionally faint, decorative sparks are removed, and microgravity has no imposed upward buoyant velocity. Oxygen and pressure remain evidence-query inputs; there is no validated mapping from them to rendered flame size, brightness or extinction. A related investigation or nearby pressure is not an exact scenario match.

## Coverage limits
The corpus is selective. Metadata, objectives, hypotheses, methods and findings retain distinct roles. Ground investigations and pending material are excluded from judged retrieval; unknown units remain unknown. There is no operational safety recommendation or calibrated combustion prediction.

Historical handoff checks are retained in HANDOFF_3_VALIDATION.json as a dated snapshot, not as the current deployment status.
