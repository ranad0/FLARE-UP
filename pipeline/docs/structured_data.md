# Structured numeric data

## Current pilot: PSI-117 Dext

Run from the project root:

```powershell
python src/normalize_dext.py
```

The normalizer reads the raw CSV and writes:

- `data/processed/structured/PSI-117_MST_2024_Dext_observations.jsonl`
- `reports/PSI-117_MST_2024_Dext_normalization_report.json`

The raw CSV is read-only input and is never rewritten by this step.

## Why this is a separate step from the file handler

The CSV handler preserves rows and headers. This Dext file contains two side-by-side series with duplicate `Pressure` labels and a blank separator column. The dataset-specific normalizer maps the left block to `model` and the right block to `experiment`. It does not pair measurements merely because they share a physical CSV row.

Each output record represents one measurement and carries its series, quantity, numeric value, original value string, pressure, source file, source row, and source column. Stable record IDs are derived from those source coordinates.

## Quality decisions and limits

- The ReadMe lists a pressure range of 0.5–1.5 atm. Model values outside that range are retained and flagged for review; they are not silently discarded.
- The CSV does not state the unit for Dext. `value_unit` remains `null` until checked against the cited publication or an authoritative dataset description.
- ReadMe conditions and citation are attached as source context, with the ReadMe row recorded.
- This JSONL is a normalized intermediate format, not a vector-embedding input. A later step can load it into SQLite or another structured query store after the team agrees on query fields and units.

## Extending the pipeline

When a new dataset has a different block layout, add a dataset-specific normalizer or a declarative mapping. Keep the raw file, record the source columns and row numbers, version the output schema, and report unexpected headers or values rather than guessing their meaning.

## Current pilot: PSI-117 Burning history

Run from the project root:

```powershell
python src/normalize_burning_history.py
python src/finalize_batch.py
```

The CSV contains six independent blocks: four experimental blocks (droplet `d^2`, flame diameter, and two separately retained `Q` blocks) and two model blocks (diameter/flame and `Q`). Their row counts differ, so the normalizer does not align samples across blocks by physical row number. Every sample retains its original CSV row and column names. Model label cells are stored as they appear and are not forward-filled.

The normalizer writes `data/processed/structured/PSI-117_MST_2024_Burning_history_Flame_diameter_samples.jsonl`; the finalizer converts its multi-measurement samples into one `time_series_observation` per quantity, adds IDs/provenance, and flags unknown time units. The per-run counts are in `reports/PSI-117_MST_2024_Burning_history_Flame_diameter_normalization_report.json`. Units explicitly present in CSV headers are attached to measurements. Time units remain unknown until verified from the cited source.

After both normalizers and chunking have run, run `python src/finalize_batch.py` once. It applies the shared schema v2.0.0 to all processed JSONL records and writes the final batch manifest and QA report. Folder labels like `PSI-117` remain unverified labels unless backed by an authoritative NASA evidence URL.
