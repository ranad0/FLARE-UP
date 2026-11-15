# Handoff 3: isolated scientific review snapshot

This is a selectively staged handoff, not the application and not an active search directory.
The source archive is `flare-up (3).zip`; its SHA-256 and full comparison are in `audit_report.json`.
Baseline application: commit `4042f2a17bf3558b6d3ddba3c6d98d6858c585cb`.

`review_decisions.json` is the explicit admission list. Only six PSI-98 CSV scalars and one
historical SAME design-objective paragraph have been admitted by `scripts/merge_handoff.py`.
The latter is archived by NASA under PSI-101/SAME-R, but is NOT a reflight result.

All other staged `data/processed` records remain pending review, regardless of labels such
as `validated_structure`, `verified`, or `scientific_text` in the original handoff. Original
metadata is preserved; this directory-level review policy overrides those labels for retrieval.
Safety-case material is supporting/contextual review material, never microgravity measurements.

The original batch manifests passed against the extracted ZIP. They describe the FULL
handoff, not this selectively staged folder. Extracted images (including 864 PSI-101 figures)
remain in the original ZIP/local audit workspace; they are not bundled or numerically digitized.
Their original manifest hashes and figure references remain available. Missing local safety
source files and the source catalog entry without a URL are unresolved review flags.

The ZIP's browser cache, executable binaries, profiles, and temporary files are excluded.
Ground PSI-117 material and the non-combustion STDCE report are excluded from admission.
Ten raw files match existing application source bytes; copies are not added again here.

The 25 newly staged raw files are received handoff material, not 25 newly verified downloads.
Only the reviewed SAME source PDF is additionally placed in the active provenance ledger.
The original 180 PSI-101 automatic chunks remain pending as a collection: admitting a separately
selected paragraph does not mark an entire overlapping automatic chunk as reviewed.
