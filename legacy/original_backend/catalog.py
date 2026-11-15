from __future__ import annotations

from collections import Counter
from typing import Any

from app.retrieval import _chunks
from app.structured_data import load_structured_records


def investigations_catalog() -> list[dict[str, Any]]:
    chunk_counts: Counter[str] = Counter()
    structured_counts: Counter[str] = Counter()
    statuses: dict[str, str] = {}
    citations: dict[str, str | None] = {}
    dois: dict[str, str | None] = {}

    for chunk in _chunks():
        label = chunk.get("investigation_id") or chunk.get("investigation_label") or chunk.get("legacy_investigation_id") or "unknown"
        chunk_counts[label] += 1
        statuses[label] = chunk.get("investigation_id_status", "unverified")
        citations[label] = chunk.get("citation_url") or citations.get(label)
        dois[label] = chunk.get("doi") or dois.get(label)

    variables: dict[str, Counter[str]] = {}
    fuels: dict[str, Counter[str]] = {}
    for record in load_structured_records():
        label = record.get("investigation_id") or record.get("investigation_label") or "unknown"
        structured_counts[label] += 1
        statuses[label] = record.get("investigation_id_status", statuses.get(label, "unverified"))
        variables.setdefault(label, Counter())[str(record.get("quantity_name") or record.get("variable") or "unknown")] += 1
        conditions = record.get("conditions") or {}
        fuel = conditions.get("Fuel") or conditions.get("fuel")
        if fuel:
            fuels.setdefault(label, Counter())[str(fuel)] += 1
        citations[label] = record.get("citation_url") or citations.get(label)
        dois[label] = record.get("doi") or dois.get(label)

    descriptions = {
        "PSI-159": {
            "title": "ACME / Cool Flames Investigation with Gases",
            "category": "combustion science",
            "platform": "International Space Station",
            "summary": "Spherical normal and inverse diffusion-flame tests across fuels, reactant dilution, flow rates, and pressures.",
        },
        "PSI-117": {
            "title": "Cool Flames in Space exploratory corpus",
            "category": "cool-flame research",
            "platform": "ISS-related / modeling context",
            "summary": "Exploratory presentation, model/experiment comparisons, and droplet-combustion time series. Canonical ID remains unverified.",
        },
    }

    labels = sorted(set(chunk_counts) | set(structured_counts))
    result: list[dict[str, Any]] = []
    for label in labels:
        meta = descriptions.get(label, {})
        result.append({
            "id": label,
            "identity_status": statuses.get(label, "unverified"),
            "title": meta.get("title", label),
            "category": meta.get("category", "NASA combustion research"),
            "platform": meta.get("platform"),
            "summary": meta.get("summary"),
            "text_chunks": chunk_counts[label],
            "structured_records": structured_counts[label],
            "top_variables": [name for name, _ in variables.get(label, Counter()).most_common(8)],
            "fuels": [name for name, _ in fuels.get(label, Counter()).most_common(10)],
            "citation_url": citations.get(label),
            "doi": dois.get(label),
        })
    return result
