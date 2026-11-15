# Local validation — 2026-11-15

No deployment, paid service, or Groq request was used for this round. The user selected retrieval/Lab testing without Groq.

## Current preview
http://127.0.0.1:8012/ serves the latest built frontend and backend together. Running ports 8010 and 8011 were found to serve older corpus versions; use 8012 for this review. The dev frontend proxy to 8010 should not be used to assess the latest data until that server is replaced.

## Checks
- 40 offline unit tests passed, including an independently reviewed synthesis revision preserving a supported interpretation (mocked provider, not a live Groq result).
- HTTP tests passed: text, structured, hybrid, English/Arabic retrieval, all four sample types, contextual-resource separation, and input validation.
- Corpus QA passed: 123 chunks, 12,160 numeric cells, original source hashes and values preserved; 122 supporting chunks remain separate.
- Browser search showed an exact NASA passage with a direct PSI citation and PDF page. Without Groq it is honestly labeled extractive; a generated answer/explanation is not claimed.
- Browser Lab liquid fuel returned PSI-39/PSI-68; fabric returned PSI-25/PSI-26. Related evidence is distinct from an exact match. No new physical prediction was introduced.
- Frontend typecheck/build and canvas reduced-motion/transition/trail checks passed.

## Refinements
Restored original Fireline three star layers (95/65/42 second drift, varied tiny sizes, restrained cross-shaped highlights). Reduced and softened the supplied logo, with a feathered edge to blend into the background. Preserved page layout.

Lab mouse disturbance gain reduced from 18 to 3; impulse caps reduced and damping increased. Slider airflow and scientific requests are unchanged. Homepage flame sensitivity is unchanged.

Removed duplicated exact-scenario warning in the Lab; its interpretation no longer refers to nearby pressure records when none were returned. Synthesis repair no longer unconditionally deletes supported interpretation. A new regression test covers that behavior.

## Remaining validation
A real generated concise answer plus interpretation needs a later, explicitly authorized Groq test. The current local session does not have a Groq key and uses the source-excerpt fallback. No deployment was performed; combine updates into one release after review.
