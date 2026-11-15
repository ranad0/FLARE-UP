# Demo review and launch improvements

The core experience works: coordinated visual modes, source-backed questions, structured comparisons and scenario evidence. The main remaining product limitation is answer readability: extraction is scientifically traceable but can be long. A future editorial summary layer must preserve evidence roles and abstention; it should not invent conclusions.

Implemented in this launch pass:
- Results scroll into view after a question, respecting reduced motion.
- Obsolete request errors cannot overwrite a newer request.
- Fire Lab loading errors offer a recovery action while Home/Evidence remain available.
- Git preserves exact bytes, protecting NASA source hashes across Windows/Linux clones.
- Netlify build settings prepared; no keys or local environments included in the repository.

Recommended next improvements:
1. Compact passage summaries with expandable exact quotations, retaining source labels.
2. More matched-condition comparisons; the scenario's pressure-only match is intentionally limited.
3. Smaller lab bundle or lower-detail rendering on weak devices. The lab is already loaded separately from Home.
4. More complete Arabic evidence UI and professionally reviewed scientific translation.
5. Validate the optional MiniLM setup before describing it as active AI; the tested default remains local lexical/latent retrieval and extractive answers.

The backend/corpus/pipeline remain unchanged in this launch pass. Deployment verification and URLs are recorded separately when available.

Final browser review fixed the desktop Fire Lab grid: long evidence no longer expands the canvas beyond the viewport. Evidence scrolls independently. Verified with the full scenario response visible.
