# Coordinated Earth / Microgravity visual system

We use one `earth | micro` visual state for the homepage flame, ambient palette, UI accents and logo tone. Fire Lab maps that state to the evidence API's gravity field.

- An 800 ms transition coordinates the original flame artwork and surrounding atmosphere.
- Earth uses an elongated amber/cream flame with a blue base; microgravity uses rounded blue/violet artwork.
- A bounded spring response gives the hero a temporary cursor disturbance. The Lab uses a much gentler response.
- Three star layers drift slowly with restrained twinkle. A faint, short continuous pointer trail fades when idle.
- Our circular flame mark and favicon use genuine transparent pixels. The wordmark shares the navigation font.
- Reduced-motion preferences suppress unnecessary movement; controls remain available.
- Fire Lab has faint smoke and no decorative sparks. Microgravity removes imposed upward buoyancy; ventilation influences transport.
- Oxygen and pressure query the evidence engine but do not predict rendered flame size, brightness or extinction.

These are authored qualitative visuals, not measured geometry, colour, temperature or timing. The evidence backend supplies scientific claims independently.

## Checks

`npm run test:visual`, `npm run typecheck` and `npm run build` validate rendering behavior and compilation. The mocked canvas checks cover reduced motion, transition completion, spring recovery, trail fading and cleanup. They are not scientific validation or a substitute for browser inspection. Current backend and corpus checks are documented in [VALIDATION.md](VALIDATION.md).
