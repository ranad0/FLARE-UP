from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import STRUCTURED_DIR

TARGET_ALIASES: dict[str, tuple[str, ...]] = {
    "extinction_diameter": ("visible flame extinction diameter", "extinction diameter"),
    "droplet_initial_diameter": ("droplet initial diameter", "initial droplet diameter"),
    "dflame": ("flame diameter", "dflame", "flame size"),
    "d_squared": ("d^2", "d²", "droplet diameter squared", "diameter squared"),
    "Q": ("heat release", "heat release rate", "power", " q "),
    "Dext_cool": ("dext_cool", "dext cool", "cool extinction diameter"),
    "Dext_hot": ("dext_hot", "dext hot", "hot extinction diameter"),
    "oxygen": ("oxygen", "xo2", "o2 concentration"),
    "pressure": ("pressure", "approx p"),
    "Tad": ("tad", "adiabatic flame temperature"),
    "Zst": ("zst", "stoichiometric mixture fraction"),
    "burn_time": ("burn time", "burn duration"),
    "peak_temperature": ("peak burner temperature", "peak burner temp", "peak temperature"),
    "fuel_burn_rate": ("fuel burn rate", "hydrocarbon burn rate", "hc burnrate", "mhc"),
    "oxygen_flow_rate": ("oxygen flow rate", "o2 flow rate"),
    "fuel_fraction": ("fuel fraction", "xf"),
}


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normal_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


@lru_cache(maxsize=1)
def load_structured_records() -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path in sorted(STRUCTURED_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                record["_structured_file"] = path.name
                if record.get('project_type') in {'Microgravity Investigation', 'Reduced Gravity Investigation'}:
                    records.append(record)
    return tuple(records)


def clear_structured_cache() -> None:
    load_structured_records.cache_clear()


def _detect_target(question: str) -> str | None:
    q = f" {question.lower()} "
    for canonical, aliases in TARGET_ALIASES.items():
        if any(alias in q for alias in aliases):
            return canonical
    if "diameter" in q and "droplet" not in q and "extinction" not in q:
        return "dflame"
    return None


def _detect_pressure(question: str) -> dict[str, float | str | None]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(atm|bar|psi)\b", question.lower())
    if not match:
        return {"value": None, "unit": None, "bar": None, "atm": None, "psi": None}
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "bar":
        bar = value
    elif unit == "atm":
        bar = value * 1.01325
    else:
        bar = value / 14.5037738
    return {
        "value": value,
        "unit": unit,
        "bar": bar,
        "atm": bar / 1.01325,
        "psi": bar * 14.5037738,
    }


def _detect_time(question: str) -> float | None:
    q = question.lower()
    for pattern in (
        r"\b(?:t|time)\s*(?:=|of|at)?\s*(\d+(?:\.\d+)?)\b",
        r"\bat\s+(\d+(?:\.\d+)?)\s*(?:s|sec|second|seconds)\b",
    ):
        match = re.search(pattern, q)
        if match:
            return float(match.group(1))
    return None


def _detect_series_type(question: str) -> str | None:
    q = question.lower()
    model = any(x in q for x in ("model", "modelled", "modeled", "prediction", "simulation"))
    experiment = any(x in q for x in ("experiment", "experimental", "measured", "measurement"))
    if model and not experiment:
        return "model"
    if experiment and not model:
        return "experiment"
    return None


def _detect_flame_type(question: str) -> str | None:
    q = question.lower()
    if re.search(r'\bnormal\b',q) and re.search(r'\binverse\b',q): return None
    normal = "normal flame" in q or "normal flames" in q
    inverse = "inverse flame" in q or "inverse flames" in q
    if normal and not inverse:
        return "normal"
    if inverse and not normal:
        return "inverse"
    return None


def _detect_fuel(question: str) -> str | None:
    q = question.lower()
    known = (
        "n-dodecane", "n-heptane", "n-decane", "dodecane", "heptane", "decane",
        "30% butane", "50% butane", "30% propane", "ethane", "propane", "butane", "ethylene", "methanol", "pentane",
        "30% ethane",
    )
    for fuel in known:
        if fuel in q:
            if fuel in {"dodecane", "heptane", "decane"}:
                return f"n-{fuel}"
            return fuel
    return None


def parse_structured_question(question: str) -> dict[str, Any]:
    q = question.lower()
    return {
        "target": _detect_target(question),
        "pressure": _detect_pressure(question),
        "time_requested": _detect_time(question),
        "series_type": _detect_series_type(question),
        "flame_type": _detect_flame_type(question),
        "fuel": _detect_fuel(question),
        "investigation": (re.search(r"psi-\d+", q).group().upper() if re.search(r"psi-\d+", q) else None),
        "distinct_fuels": bool(re.search(r"\b(?:what|which)\s+fuels?\b|fuels?\s+(?:were|are)\s+tested", q)),
        "compare_flame_types": "compare" in q and "normal" in q and "inverse" in q,
    }


def _schema_unit(record: dict[str, Any]) -> Any:
    return record.get("unit") if "unit" in record else record.get("value_unit")


def _row_values(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record.get("source_row_values") or {})


def _conditions(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record.get("conditions") or {})


def _record_fuel(record: dict[str, Any]) -> str | None:
    conditions = _conditions(record)
    return conditions.get("Fuel") or conditions.get("fuel")


def _record_flame_type(record: dict[str, Any]) -> str | None:
    value = _conditions(record).get("Flame Type")
    return _normal_name(value) or None


def _record_pressure_bar(record: dict[str, Any]) -> float | None:
    if record.get("pressure_atm") is not None:
        value = _float(record.get("pressure_atm"))
        return value * 1.01325 if value is not None else None
    row = _row_values(record)
    if _float(row.get("Ambient pressure; mmHg")) is not None:
        return float(row["Ambient pressure; mmHg"])/760*1.01325
    for key in ("pmean (atm)","Ambient Pressure (atm)"):
        if _float(row.get(key)) is not None: return float(row[key])*1.01325
    inline = re.fullmatch(r"\s*([0-9.]+)\s*atm\s*", str(row.get("Pressure", "")),re.I)
    if inline: return float(inline.group(1))*1.01325
    for key in ("approx p (bar)", "Pressure (bar)", "pressure_bar"):
        if key in row:
            return _float(row.get(key))
    if _normal_name(record.get("quantity_name")) == "approx p bar":
        return _float(record.get("value"))
    conditions = _conditions(record)
    pressure = conditions.get("pressure") or {}
    value = _float(pressure.get("raw_value"))
    unit = _normal_name(pressure.get("unit"))
    if value is not None:
        if unit == "atm":
            return value * 1.01325
        if unit == "bar":
            return value
        if unit == "psi":
            return value / 14.5037738
    return None


def _quantity_matches(target: str | None, name: Any) -> bool:
    if target is None:
        return True
    normalized = _normal_name(name)
    if target == "Dext_cool":
        return normalized in {"dext cool", "dext cool expt"}
    if target == "Dext_hot":
        return normalized in {"dext hot", "dext hot expt"}
    rules = {
        "extinction_diameter": lambda n: "extinction diameter" in n,
        "droplet_initial_diameter": lambda n: "droplet initial diameter" in n,
        "dflame": lambda n: "dflame" in n or "flame diameter" in n,
        "d_squared": lambda n: n in {"d 2", "d2", "droplet diameter squared"},
        "Q": lambda n: n == "q" or "heat release" in n,
        "oxygen": lambda n: "xo2" in n or "oxygen" in n,
        "pressure": lambda n: "approx p" in n or "pressure" in n,
        "Tad": lambda n: n == "tad k" or n.startswith("tad"),
    "Zst": lambda n: n in {"zst", "mean zst"},
        "burn_time": lambda n: ("burn time" in n or "burn duration" in n),
        "peak_temperature": lambda n: "peak burner" in n,
        "fuel_burn_rate": lambda n: "burnrate" in n or "mhc" in n or "fuel burn rate" in n or "burning rate" in n or "mfuel" in n,
        "oxygen_flow_rate": lambda n: "o2 flow rate" in n or "oxygen flow rate" in n or "mo2" in n,
        "fuel_fraction": lambda n: n == "xf" or n.startswith("xf before") or n.startswith("xf after"),
    }
    return rules.get(target, lambda n: n == _normal_name(target))(normalized)


def _matches(record: dict[str, Any], parsed: dict[str, Any]) -> bool:
    if record.get("record_type") not in {"numeric_observation", "time_series_sample"}:
        return False

    requested_investigation = parsed.get("investigation")
    label = record.get("investigation_id") or record.get("investigation_label")
    if requested_investigation and label != requested_investigation:
        return False

    requested_series = parsed.get("series_type")
    if requested_series and _normal_name(record.get("series_type")) != requested_series:
        return False

    requested_fuel = parsed.get("fuel")
    if requested_fuel and _normal_name(_record_fuel(record)) != _normal_name(requested_fuel):
        return False

    requested_flame = parsed.get("flame_type")
    if requested_flame and _record_flame_type(record) != requested_flame:
        return False

    pressure = parsed.get("pressure") or {}
    if pressure.get("bar") is not None:
        record_pressure = _record_pressure_bar(record)
        # Approximate-pressure tables justify a small tolerance.
        if record_pressure is None or abs(record_pressure - pressure["bar"]) > 0.015:
            return False

    if not _quantity_matches(parsed.get("target"), record.get("quantity_name") or record.get("variable")):
        if record.get("record_type") == "time_series_sample":
            measurements = record.get("measurements") or []
            if not any(_quantity_matches(parsed.get("target"), item.get("name")) for item in measurements):
                return False
        else:
            return False

    return True


def _public_numeric(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "numeric_observation",
        "schema_version": record.get("schema_version"),
        "record_id": record.get("record_id"),
        "investigation_id": record.get("investigation_id"),
        "investigation_label": record.get("investigation_label") or record.get("investigation_id"),
        "investigation_id_status": record.get("investigation_id_status", "unverified"),
        "dataset_id": record.get("dataset_id"),
        "series_type": record.get("series_type"),
        "quantity_name": record.get("quantity_name"),
        "project_type": record.get("project_type"),
        "source_sha256": record.get("source_sha256"),
        "value": record.get("value"),
        "value_raw": record.get("value_raw"),
        "unit": _schema_unit(record),
        "unit_status": record.get("unit_status"),
        "pressure_bar": _record_pressure_bar(record),
        "conditions": _conditions(record),
        "quality_flags": record.get("quality_flags") or [],
        "source_file": record.get("source_file"),
        "source_location": record.get("source_location") or (
            f"row:{record.get('source_row_number')}" if record.get("source_row_number") else None
        ),
        "source_row_number": record.get("source_row_number"),
        "source_column_name": record.get("source_column_name"),
        "citation_url": record.get("citation_url"),
        "doi": record.get("doi") or _conditions(record).get("reference_doi"),
    }


def _time_series_results(records: list[dict[str, Any]], parsed: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for record in records:
        if record.get("record_type") != "time_series_sample" or not _matches(record, parsed):
            continue
        for measurement in record.get("measurements") or []:
            if _quantity_matches(parsed.get("target"), measurement.get("name")):
                key = (record.get("series_id") or "unknown", measurement.get("name") or "unknown")
                groups[key].append((record, measurement))

    requested_time = parsed.get("time_requested")
    output: list[dict[str, Any]] = []
    for (series_id, name), samples in groups.items():
        if requested_time is not None:
            record, measurement = min(
                samples,
                key=lambda pair: abs((_float((pair[0].get("time") or {}).get("value")) or 0.0) - requested_time),
            )
            output.append({
                "kind": "time_series_nearest",
                "series_id": series_id,
                "measurement_name": name,
                "requested_time": requested_time,
                "matched_time": (record.get("time") or {}).get("value"),
                "time_unit": (record.get("time") or {}).get("unit"),
                "value": measurement.get("value"),
                "unit": measurement.get("unit"),
                "conditions": record.get("conditions"),
                "source_file": record.get("source_file"),
                "source_row_number": record.get("source_row_number"),
            })
        else:
            values = [_float(measurement.get("value")) for _, measurement in samples]
            values = [value for value in values if value is not None]
            if not values:
                continue
            record, measurement = samples[0]
            output.append({
                "kind": "time_series_summary",
                "series_id": series_id,
                "series_type": record.get("series_type"),
                "measurement_name": name,
                "sample_count": len(values),
                "min_value": min(values),
                "max_value": max(values),
                "unit": measurement.get("unit"),
                "conditions": record.get("conditions"),
                "source_file": record.get("source_file"),
                "source_rows_note": "Calculated range over validated structured samples.",
            })
    return output[:limit]


def _fuel_facets(records: list[dict[str, Any]], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    for record in records:
        label = record.get("investigation_id") or record.get("investigation_label") or "unknown"
        if parsed.get("investigation") and label != parsed["investigation"]:
            continue
        fuel = _record_fuel(record)
        if fuel:
            counter[(label, str(fuel))] += 1
    return [
        {"kind": "facet", "facet": "fuel", "investigation": key[0], "value": key[1], "record_mentions": count}
        for key, count in counter.most_common()
    ]


def search_structured(question: str, limit: int = 16) -> dict[str, Any]:
    parsed = parse_structured_question(question)
    records = list(load_structured_records())
    if not parsed.get('target') and not parsed.get('distinct_fuels'):
        return {'question':question,'parsed':parsed,'results':[],'result_count':0,'warning':'Specify a supported quantity such as burn time, Tad, oxygen, pressure, or extinction diameter.'}

    if parsed.get("distinct_fuels"):
        results = _fuel_facets(records, parsed)[:limit]
    else:
        numeric = [_public_numeric(record) for record in records if record.get("record_type") == "numeric_observation" and _matches(record, parsed)]
        time_series = _time_series_results(records, parsed, limit)
        if parsed.get('compare_flame_types'):
            # Interleave both groups so truncation does not silently hide one side.
            normal=[r for r in numeric if _record_flame_type(r)=='normal']
            inverse=[r for r in numeric if _record_flame_type(r)=='inverse']
            numeric=[r for pair in __import__('itertools').zip_longest(normal,inverse) for r in pair if r is not None]
        total_matches=len(numeric)+len(time_series)
        results=(numeric+time_series)[:limit]

    return {
        "question": question,
        "parsed": parsed,
        "result_count": len(results),
        "total_matches": locals().get('total_matches',len(results)),
        "results": results,
        "warning": (
            "Values are returned from validated structured records. Null units stay unknown. "
            "Judged corpus excludes Ground Investigations. Pressure filters use a stated tolerance of 0.015 bar. Results are source records, not predictions."
        ),
    }


def structured_stats() -> dict[str, Any]:
    records = list(load_structured_records())
    investigations: Counter[str] = Counter()
    quantities: Counter[str] = Counter()
    schemas: Counter[str] = Counter()
    verified: Counter[str] = Counter()
    for record in records:
        label = record.get("investigation_id") or record.get("investigation_label") or "unknown"
        investigations[label] += 1
        quantities[str(record.get("quantity_name") or record.get("variable") or record.get("record_type"))] += 1
        schemas[str(record.get("schema_version") or "unknown")] += 1
        verified[str(record.get("investigation_id_status") or "unverified")] += 1
    return {
        "record_count": len(records),
        "investigations": dict(investigations),
        "top_quantities": dict(quantities.most_common(20)),
        "schema_versions": dict(schemas),
        "identity_status": dict(verified),
    }
