# Reviewed evidence expansion — 15 November 2026

Ten reviewed text sections were added from two existing NASA PSI reports. These additions improve coverage of flame appearance, buoyancy, ventilation, fabric extinction, polymer ignition and quenching. They do not add measurements or validate the Fire Lab's combined settings.

| Investigation | PDF pages | Evidence scope |
| --- | --- | --- |
| PSI-23, ACME s-Flame | 3, 4 | Historical experiment design and microgravity rationale; not measured findings |
| PSI-25, BASS-II | 9, 19, 28, 36, 54, 72, 97, 109 | ISS methods, qualified scientific background, and material-specific observations/conclusions |

NASA's official investigation metadata was checked again before admission. Both are Combustion Science / Microgravity Investigation. DOIs: PSI-23 `10.60555/k57n-p030`; PSI-25 `10.60555/4qc4-de67`.

The [review manifest](../backend/data/meta/review_additions_2026-11-15.json) records exact selection boundaries, original file hashes, approved text hashes, roles and limitations. The existing corpus adapter reads this allowlist and checks it during rebuild. The authoritative team ingestion pipeline is unchanged. Full source files remain immutable.

No figure was digitized. Ground comparisons, equations and table cells were not promoted as new measurements. The chemistry-name inconsistency on CFI report page 7 was left out. Research rationale is labelled separately from findings; Nomex and candle observations remain specific to the reported tests.

## Coverage after this review

- 19 eligible investigations, all partially ingested; no new investigation IDs.
- 41 existing active source files; no new downloads claimed.
- 123 active text chunks: 61 official metadata passages and 62 reviewed PDF passages.
- 2,001 structured source rows; 12,160 scalar records; 2,737 records retain unknown units.
- 122 supporting NASA chunks remain separate from judged evidence.
- The archived full-report extraction remains a review collection; only approved selections enter default retrieval.

All structured records are byte-for-byte unchanged from before this expansion (SHA-256 `36964de01a980d8e82f59aa4298363753d26770cd60236ea4845e51526919749`). Corpus QA checks source hashes, original values, duplicate IDs and eligibility.

## Search and Fire Lab

Arabic topic expansion now handles common spellings and questions about fire in space. It changes query terms, never source text. The original text / structured / hybrid routes remain; generated numbers are still prohibited. Groq receives retrieved evidence, and the server checks source references, numerical assertions and experimental scope before returning prose. A short explanation is requested when supported. Provider or grounding failures retain a labelled extractive fallback.

Fire Lab distinguishes related material research from pressure-comparable records and exact experimental matches. It shows related investigation IDs even when there are no comparable numeric rows. Exact-match status remains false when oxygen, fuel composition, geometry or airflow cannot be validated. The controls are not a physical combustion solver.
