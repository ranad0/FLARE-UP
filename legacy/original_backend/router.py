from __future__ import annotations

import re

NUMERIC_TERMS = {
    "value", "values", "number", "numeric", "measurement", "measurements",
    "diameter", "dflame", "dext", "d^2", "d²", "heat release", "burning rate",
    "burn rate", "pressure", "temperature", "time", "model", "experiment",
    "experimental", "predicted", "measured", "atm", "bar", "psi", "mm", "mg/s",
    "tad", "zst", "xo2", "oxygen concentration", "burn time", "peak burner",
    "flow rate", "normal flame", "inverse flame", "fuels tested", "which fuels",
}

INTERPRETIVE_TERMS = {
    "why", "explain", "interpret", "meaning", "mean", "implication", "what does",
    "what do", "سبب", "اشرح", "فسر", "لماذا", "ليش",
}


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def route_question(question: str) -> dict[str, str | int | bool]:
    q = " ".join(question.lower().split())
    numeric_hits = sum(1 for term in NUMERIC_TERMS if term in q)
    has_number = bool(re.search(r"(?<![a-z])\d+(?:\.\d+)?", q))
    has_unit = bool(re.search(r"\b(?:atm|bar|psi|mm|mg/s|k|c|sec|seconds?)\b", q))
    asks_interpretation = _contains_any(q, INTERPRETIVE_TERMS)
    has_measurement = numeric_hits > 0

    quantitative = has_measurement or has_unit or (has_number and numeric_hits >= 1)

    if quantitative and asks_interpretation:
        route = "hybrid"
        reason = "The question combines quantitative evidence with interpretation."
    elif quantitative:
        route = "structured"
        reason = "The question requests exact conditions, measurements, or dataset facets."
    else:
        route = "text"
        reason = "The question is descriptive, so semantic retrieval is the best first path."

    return {
        "route": route,
        "reason": reason,
        "numeric_term_hits": numeric_hits,
        "has_number": has_number,
        "has_unit": has_unit,
        "has_measurement_target": has_measurement,
        "asks_interpretation": asks_interpretation,
    }
