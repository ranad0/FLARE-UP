from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.structured_data import load_structured_records


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _oxygen_percent(row: dict[str, Any]) -> float | None:
    for key in ("XO2", "XO2 before test", "XO2  after test"):
        value = _float(row.get(key))
        if value is not None:
            return value * 100.0 if value <= 1.0 else value
    return None


def _pressure_psi(row: dict[str, Any], record: dict[str, Any]) -> float | None:
    value = _float(row.get("approx p (bar)"))
    if value is not None:
        return value * 14.5037738
    value = _float(record.get("pressure_atm"))
    if value is not None:
        return value * 14.6959
    return None


def _fuel(record: dict[str, Any]) -> str | None:
    conditions = record.get("conditions") or {}
    return conditions.get("Fuel") or conditions.get("fuel")


def _material_affinity(sample_type: str, fuel: str | None, investigation: str) -> float:
    sample = sample_type.lower()
    fuel_text = (fuel or "").lower()
    if sample == "liquid fuel" and ("dodecane" in fuel_text or investigation == "PSI-117"):
        return 1.0
    if sample in {"fabric", "polymer"}:
        return 0.2
    if sample == "gaseous fuel" and investigation == "PSI-159":
        return 1.0
    return 0.5


def closest_scenario_matches(
    *, oxygen_percent: float, pressure_psi: float, gravity: str, sample_type: str, limit: int = 5
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], dict[str, Any]] = {}
    for record in load_structured_records():
        if record.get("record_type") != "numeric_observation":
            continue
        investigation = record.get("investigation_id") or record.get("investigation_label") or "unknown"
        row_number = int(record.get("source_row_number") or 0)
        key = (investigation, str(record.get("source_file")), row_number)
        group = grouped.setdefault(
            key,
            {
                "investigation": investigation,
                "investigation_id_status": record.get("investigation_id_status", "unverified"),
                "source_file": record.get("source_file"),
                "source_row_number": row_number,
                "citation_url": record.get("citation_url"),
                "conditions": record.get("conditions") or {},
                "row_values": record.get("source_row_values") or {},
                "fuel": _fuel(record),
                "measurements": {},
            },
        )
        group["measurements"][str(record.get("quantity_name"))] = {
            "value": record.get("value"),
            "unit": record.get("unit") if "unit" in record else record.get("value_unit"),
        }

    matches: list[dict[str, Any]] = []
    for group in grouped.values():
        oxygen = _oxygen_percent(group["row_values"])
        pressure = _pressure_psi(group["row_values"], {
            "pressure_atm": group["measurements"].get("pressure_atm", {}).get("value")
        })
        # PSI-117 normalized records keep pressure in conditions/record rather than row values.
        if pressure is None:
            conditions = group.get("conditions") or {}
            if "pressure_range_atm_listed_in_readme" in conditions:
                values = conditions["pressure_range_atm_listed_in_readme"]
                if values:
                    pressure = float(values[0]) * 14.6959
            oxygen_map = conditions.get("mixture_mole_fractions_as_listed") or {}
            if oxygen is None and oxygen_map.get("XO2") is not None:
                oxygen = float(oxygen_map["XO2"]) * 100.0

        oxygen_distance = abs((oxygen if oxygen is not None else 21.0) - oxygen_percent) / 25.0
        pressure_distance = abs((pressure if pressure is not None else 14.7) - pressure_psi) / 12.0
        material_score = _material_affinity(sample_type, group.get("fuel"), group["investigation"])
        gravity_score = 1.0 if gravity.lower() == "microgravity" else 0.45
        score = max(0.0, min(1.0, 1.0 - 0.4 * oxygen_distance - 0.35 * pressure_distance))
        score = score * 0.65 + material_score * 0.2 + gravity_score * 0.15

        matches.append({
            "match_score": round(score, 3),
            "investigation": group["investigation"],
            "investigation_id_status": group["investigation_id_status"],
            "fuel": group.get("fuel"),
            "oxygen_percent": round(oxygen, 3) if oxygen is not None else None,
            "pressure_psi": round(pressure, 3) if pressure is not None else None,
            "source_file": group["source_file"],
            "source_row_number": group["source_row_number"],
            "citation_url": group.get("citation_url"),
            "selected_measurements": {
                key: value for key, value in group["measurements"].items()
                if any(token in key.lower() for token in ("tad", "burn time", "peak burner", "dext"))
            },
        })

    matches.sort(key=lambda item: item["match_score"], reverse=True)
    return matches[:limit]


def evidence_level(matches: list[dict[str, Any]], sample_type: str) -> str:
    if not matches:
        return "Gap"
    top = matches[0]["match_score"]
    if sample_type.lower() in {"fabric", "polymer"}:
        return "Limited"
    if top >= 0.86:
        return "Close"
    if top >= 0.65:
        return "Limited"
    return "Gap"


def visual_state(*, gravity: str, oxygen_percent: float, pressure_psi: float, airflow: float, material: str) -> dict[str, Any]:
    micro = gravity.lower() == "microgravity"
    oxygen_factor = max(0.0, min(1.0, (oxygen_percent - 15.0) / 25.0))
    pressure_factor = max(0.0, min(1.0, (pressure_psi - 4.3) / 10.4))
    material_smoke = {"fabric": 0.78, "polymer": 0.92, "liquid fuel": 0.36, "gaseous fuel": 0.15}.get(material.lower(), 0.45)
    return {
        "roundness": 0.9 if micro else 0.25,
        "elongation": 0.95 if micro else 1.65,
        "blue_bias": 0.86 if micro else 0.34,
        "intensity": round(0.62 + oxygen_factor * 0.38, 3),
        "pressure_response": round(0.85 + pressure_factor * 0.15, 3),
        "airflow_deformation": round(max(0.0, min(1.0, airflow / 3.0)), 3),
        "illustrative_smoke": material_smoke,
        "disclaimer": "Evidence-informed visualization — not a numerical combustion simulation.",
    }
