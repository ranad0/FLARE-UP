from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

HF_EMBED_MODEL = os.getenv(
    "HF_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

LOCAL_VECTOR_INDEX = Path(
    os.getenv("LOCAL_VECTOR_INDEX", str(BACKEND_ROOT / "storage" / "vector_index.json"))
)
CHUNKS_PATH = Path(os.getenv("CHUNKS_PATH", str(BACKEND_ROOT / "data" / "chunks.jsonl")))
STRUCTURED_DIR = Path(
    os.getenv("STRUCTURED_DIR", str(BACKEND_ROOT / "data" / "structured"))
)
DATA_META_DIR = BACKEND_ROOT / "data" / "meta"
TOP_K = int(os.getenv("TOP_K", "7"))

ALLOWED_ORIGINS = [
    value.strip()
    for value in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if value.strip()
]
