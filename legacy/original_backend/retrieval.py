from __future__ import annotations

import json
import re
from functools import lru_cache

from app.config import CHUNKS_PATH, TOP_K
from app.embedder import embed_query
from app.vector_store import search_chunks


@lru_cache(maxsize=1)
def _chunks() -> tuple[dict, ...]:
    rows: list[dict] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return tuple(rows)


def _result(payload: dict, score: float, method: str) -> dict:
    return {
        "score": float(score),
        "retrieval_method": method,
        "chunk_id": payload.get("chunk_id"),
        "investigation_id": payload.get("investigation_id"),
        "investigation_label": payload.get("investigation_label") or payload.get("legacy_investigation_id") or payload.get("investigation_id"),
        "investigation_id_status": payload.get("investigation_id_status", "unverified"),
        "content_type": payload.get("content_type"),
        "source_record_type": payload.get("source_record_type"),
        "source_file": payload.get("source_file"),
        "source_relative_path": payload.get("source_relative_path"),
        "source_location": payload.get("source_location"),
        "citation_url": payload.get("citation_url"),
        "doi": payload.get("doi"),
        "text": payload.get("text"),
        "source_schema_version": payload.get("source_schema_version"),
    }


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _lexical_rank(question: str, limit: int) -> list[dict]:
    query = _tokens(question)
    if not query:
        return []
    query_set = set(query)
    scored: list[tuple[float, dict]] = []
    for chunk in _chunks():
        text = f"{chunk.get('embedding_text', '')} {chunk.get('text', '')}"
        words = _tokens(text)
        word_set = set(words)
        overlap = sum(1 for term in query if term in word_set)
        phrase_bonus = sum(1 for pair in zip(query, query[1:]) if " ".join(pair) in text.lower())
        if overlap:
            score = overlap / max(1, len(query)) + phrase_bonus * 0.08
            scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_result(chunk, score, "lexical") for score, chunk in scored[:limit]]


def _semantic_rank(question: str, limit: int) -> list[dict]:
    query_vector = embed_query(question)
    return [_result(dict(hit.payload or {}), hit.score, "minilm-cosine") for hit in search_chunks(query_vector, limit=limit)]


def _fuse(semantic: list[dict], lexical: list[dict], limit: int) -> list[dict]:
    combined: dict[str, dict] = {}
    scores: dict[str, float] = {}
    for weight, rows in ((1.0, semantic), (0.72, lexical)):
        for rank, row in enumerate(rows, start=1):
            key = str(row.get("chunk_id"))
            combined.setdefault(key, row)
            scores[key] = scores.get(key, 0.0) + weight / (50 + rank)
    ordered = sorted(combined, key=lambda key: scores[key], reverse=True)[:limit]
    result: list[dict] = []
    for key in ordered:
        row = dict(combined[key])
        row["fusion_score"] = scores[key]
        if key in {str(item.get("chunk_id")) for item in semantic} and key in {str(item.get("chunk_id")) for item in lexical}:
            row["retrieval_method"] = "hybrid-vector-lexical"
        result.append(row)
    return result


def search_text(question: str, limit: int | None = None) -> list[dict]:
    wanted = limit or TOP_K
    lexical = _lexical_rank(question, wanted * 2)
    try:
        semantic = _semantic_rank(question, wanted * 2)
    except Exception:
        semantic = []
    return _fuse(semantic, lexical, wanted) if semantic else lexical[:wanted]
