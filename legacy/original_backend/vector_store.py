from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import LOCAL_VECTOR_INDEX


@dataclass
class SearchHit:
    score: float
    payload: dict[str, Any]


def _empty_index(vector_size: int) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "vector_size": vector_size,
        "distance": "cosine",
        "items": [],
    }


@lru_cache(maxsize=1)
def _load_index_cached() -> dict[str, Any]:
    if not LOCAL_VECTOR_INDEX.exists():
        raise RuntimeError(
            f"Vector index not found at {LOCAL_VECTOR_INDEX}. "
            "Run: python -m scripts.index_chunks"
        )
    with LOCAL_VECTOR_INDEX.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def clear_index_cache() -> None:
    _load_index_cached.cache_clear()


def _save_index(index: dict[str, Any]) -> None:
    LOCAL_VECTOR_INDEX.parent.mkdir(parents=True, exist_ok=True)
    temporary = LOCAL_VECTOR_INDEX.with_suffix(LOCAL_VECTOR_INDEX.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(index, stream, ensure_ascii=False, separators=(",", ":"))
    temporary.replace(LOCAL_VECTOR_INDEX)
    clear_index_cache()


def reset_collection(vector_size: int) -> None:
    _save_index(_empty_index(vector_size))


def add_chunks(chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors must have the same length")
    if not vectors:
        return

    index = _load_index_cached()
    expected_size = int(index.get("vector_size") or 0)

    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != expected_size:
            raise ValueError(
                f"Vector size mismatch for {chunk.get('chunk_id')}: "
                f"got {len(vector)}, expected {expected_size}"
            )
        index["items"].append(
            {"vector": [float(value) for value in vector], "payload": chunk}
        )

    _save_index(index)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_chunks(vector: list[float], limit: int = 7) -> list[SearchHit]:
    index = _load_index_cached()
    expected_size = int(index.get("vector_size") or 0)
    if len(vector) != expected_size:
        raise ValueError(
            f"Query vector size {len(vector)} does not match index size {expected_size}."
        )

    hits: list[SearchHit] = []
    for item in index.get("items", []):
        stored = item.get("vector") or []
        if len(stored) != expected_size:
            continue
        hits.append(
            SearchHit(
                score=float(_cosine_similarity(vector, stored)),
                payload=dict(item.get("payload") or {}),
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]


def index_stats() -> dict[str, Any]:
    index = _load_index_cached()
    investigations: dict[str, int] = {}
    for item in index.get("items", []):
        payload = item.get("payload") or {}
        label = (
            payload.get("investigation_id")
            or payload.get("investigation_label")
            or "unknown"
        )
        investigations[label] = investigations.get(label, 0) + 1
    return {
        "path": str(LOCAL_VECTOR_INDEX),
        "vector_size": index.get("vector_size"),
        "chunk_count": len(index.get("items", [])),
        "investigations": investigations,
    }
