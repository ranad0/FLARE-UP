# FLARE UP — submission checklist

Project: **FLARE UP — Flame in Freefall**

Primary demo: https://flare-up-ranad0.netlify.app/
Full-app alternate endpoint: https://flare-up-ranad0.onrender.com/ (free service may need time to wake; verify before recording).
Code: https://github.com/ranad0/FLARE-UP

## Public summary
FLARE UP makes NASA microgravity combustion research accessible through an interactive evidence platform. Users can ask questions, inspect cited scientific passages, compare validated measurements, and explore an illustrative Fire Lab. Text, structured and hybrid retrieval remain separate and traceable. Optional Groq synthesis provides concise explanations grounded in retrieved sources; numbers are rendered from structured records. The platform makes missing evidence explicit instead of presenting unsupported predictions.

## NASA and AI use
The judged corpus covers selected content from 19 verified microgravity investigations: 123 selected text chunks, 2,001 structured source rows and 12,160 scalar records. Coverage is partial, not complete ingestion of NASA PSI. Supporting NASA resources are separate. Ground PSI-117 material is excluded. Unknown units remain unknown. See the provenance report and EVIDENCE_EXPANSION.md.

Groq openai/gpt-oss-20b is optional and uses the Groq endpoint, not the OpenAI API. Generated claims carry citations and undergo automated checks, which do not replace scientific review. If unavailable, original excerpts and validated records remain usable.

## Record a short demo
Use the seven-slide narration in DEMO_SCRIPT.md. Show Earth/microgravity, a text question with sources, a numeric comparison, and the Fire Lab. Demonstrate one unavailable exact scenario rather than claiming prediction accuracy. The Lab smoke is deliberately faint, has no default sparks, and has no buoyant upward drift in microgravity. Visibility and motion are illustrative, not measured rates or emissions.

## Before submitting
- Open primary URL in a fresh browser and confirm search and Lab.
- Choose one text question that has been verified with the current provider status; do not label fallback excerpts as generated answers.
- Capture or record the seven-slide demo; check the challenge portal's current format/length rules.
- Confirm team names, contributor profiles, summary, NASA references, public code and demo URLs in the submission form.
- Keep the archive and local app ready as a backup. No paid upgrade or alternate account is required for this release.

## Cost control
Keep the existing free plans. Bundle changes into releases; avoid repeated production deploys. Do not assume account transfers reset limits. Check hosting availability before the judging demo.
