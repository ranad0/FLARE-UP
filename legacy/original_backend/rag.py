from __future__ import annotations

import json

from app.groq_llm import generate_grounded_answer
from app.retrieval import search_text
from app.router import route_question
from app.structured_data import search_structured


def _text_block(results: list[dict]) -> str:
    if not results:
        return "TEXT EVIDENCE\nNo relevant text evidence was retrieved."
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        identity = item.get("investigation_id") or item.get("investigation_label")
        blocks.append("\n".join([
            f"TEXT SOURCE {index}",
            f"Investigation: {identity} ({item.get('investigation_id_status')})",
            f"Content type: {item.get('content_type')}",
            f"File: {item.get('source_file')}",
            f"Location: {item.get('source_location')}",
            f"Citation URL: {item.get('citation_url') or 'not provided'}",
            f"DOI: {item.get('doi') or 'not provided'}",
            f"Retrieval score: {item.get('score'):.4f}",
            "Content:",
            item.get("text") or "",
        ]))
    return "\n\n---\n\n".join(blocks)


def _structured_block(structured: dict) -> str:
    results = structured.get("results") or []
    if not results:
        return "STRUCTURED EVIDENCE\nNo structured record matched. Do not infer numbers from prose."
    blocks = [
        "STRUCTURED EVIDENCE",
        "Parsed query: " + json.dumps(structured.get("parsed") or {}, ensure_ascii=False),
        "Null units remain unknown.",
    ]
    for index, item in enumerate(results, start=1):
        blocks.append(f"STRUCTURED RECORD {index}\n" + json.dumps(item, ensure_ascii=False, indent=2))
    return "\n\n---\n\n".join(blocks)


def ask_flare_up(question: str) -> dict:
    decision = route_question(question)
    route = str(decision["route"])
    text_results: list[dict] = []
    structured = {"parsed": {}, "results": []}
    evidence_parts: list[str] = []

    if route in {"text", "hybrid"}:
        text_results = search_text(question)
        evidence_parts.append(_text_block(text_results))
    if route in {"structured", "hybrid"}:
        structured = search_structured(question)
        evidence_parts.append(_structured_block(structured))

    answer, llm_status = generate_grounded_answer(
        question,
        "\n\n====================\n\n".join(evidence_parts),
    )
    return {
        "question": question,
        "route": route,
        "routing_reason": decision["reason"],
        "answer": answer,
        "llm_status": llm_status,
        "sources": text_results,
        "structured_query": structured.get("parsed") or {},
        "structured_results": structured.get("results") or [],
        "notes": [
            "Text questions use MiniLM semantic retrieval.",
            "Numeric questions use validated structured records.",
            "Hybrid questions combine both paths.",
            "PSI-117 is unverified; PSI-159 is verified.",
        ],
    }
