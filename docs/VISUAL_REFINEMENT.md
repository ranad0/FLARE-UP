# Reference visual refinement — local preview

The approved homepage hierarchy, large question, search form, and bottom Fire Lab entry are retained.

- Restored the Earth flame and blue microgravity dome artwork from Fireline v17, using the existing shared visual mode, an 800 ms blend, and damped pointer disturbance.
- Reused the original user-supplied circular flame image in the navbar and favicon. The source PNG is preserved unchanged; CSS frames it for the navbar.
- Restored indigo/blue atmosphere and muted gold controls, with warmer Earth glow and slightly clearer tiny stars.
- Added a round globe button with explicit Arabic/English choices, selected-language indication, keyboard focus, and Escape dismissal.
- Replaced scattered cursor sparks with a short, low-opacity continuous trail. It fades within 420 ms, stops rendering while idle, and is disabled for touch and reduced motion.

Validation: frontend typecheck, production build, and canvas behavior checks passed. Chrome desktop and 390px mobile were inspected; language switching and both gravity modes worked. No backend, corpus, ingestion, routing, or API changes are included.

Deployment: local only. No Netlify upload, Render deployment, or additional Groq request was made for this visual refinement. Local preview: http://127.0.0.1:5174/

Live synthesis remains a separate follow-up: the previously saved Arabic behavior test was Groq-grounded, while Arabic ignition and English appearance tests fell back after Groq TPM rate limits. These are not claimed as successful generated answers. Paid upgrades were not enabled.
