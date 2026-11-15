# Coordinated Earth / Microgravity visual system

The integrated frontend now restores the coordinated atmosphere from Fireline v17's `hero-flame.js`, `style.css`, `app.js` and `index.html`. The old layout and canned answers were not restored.

`App.tsx` owns one explicit `earth | micro` state. It drives the hero canvas, navbar flame canvas, cursor canvas and root `data-visual-mode`. CSS transitions the page gradient, ambient halos, search border/shadow, buttons and surfaces. Fire Lab gravity controls update this same state; the existing API still receives `earth | microgravity` through an explicit frontend mapping.

- 800ms eased geometry morph and palette/halo crossfade, including interrupted transitions.
- Earth: elongated warm flame, blue base, upward luminous movement, warm rising/tapering cursor particles.
- Microgravity: full electric-blue/cyan sphere with violet interior, wider cool halos, radial cursor diffusion.
- Cursor velocity produces a bounded spring impulse near the hero; the halo follows more slowly, then both recover.
- 234 tiny cream/white/violet stars in three stable depth layers, drifting over 55/80/110 seconds with restrained twinkle.
- Navbar uses the same renderer as the hero; SVG favicon uses the related spherical shell/arc mark, with no generic droplet.
- Reduced motion: hero/logo draw statically, pointer disturbance and cursor emission are disabled, CSS star motion/twinkle/transitions stop. Fire Lab's decorative flame time, smoke and ember motion freeze; user controls remain functional.
- Canvas device pixel ratio is capped at 2. Cursor count is capped at 100; its animation loop stops when empty. Hero pauses while hidden and cleans up observers/listeners on unmount.

The art is an explanatory visual metaphor, not measured flame geometry, temperature, colour, rate or timing. The visible simulation disclaimer remains. Source claims still come from the unchanged backend.

## Verification
From `frontend`: `npm run test:visual`, `npm run typecheck`, `npm run build`.

The renderer tests execute the compiled canvas effects in a mocked DOM/canvas scheduler: Earth and micro geometry, intermediate morph, directional impulse/recovery, reduced-motion scheduling and live preference changes, particle emission/cleanup, rising versus radial motion. They are behavioral checks, not a calibrated scientific model or browser pixel comparison.

Chrome verification covers both actual palettes and logos, shared mode DOM attributes, 3 layers/234 stars, the 0.8s CSS transition, mobile layout, real Ask results and Fire Lab evidence sections. Reduced-motion behavior is exercised by the renderer harness and CSS review; no operating-system accessibility settings were changed.

The current backend, data, ingestion scripts and existing tests were SHA-256 compared with their pre-edit baseline and remain byte-for-byte unchanged. All 15 existing backend tests, corpus QA and HTTP tests pass.
