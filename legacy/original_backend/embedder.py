from __future__ import annotations

from functools import lru_cache

from app.config import HF_EMBED_MODEL


@lru_cache(maxsize=1)
def _components():
    # Lazy imports keep the API and lexical fallback usable even before the
    # optional local embedding stack has been installed or downloaded.
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(max(1, min(2, torch.get_num_threads())))
    tokenizer = AutoTokenizer.from_pretrained(HF_EMBED_MODEL)
    model = AutoModel.from_pretrained(HF_EMBED_MODEL)
    model.eval()
    return torch, functional, tokenizer, model


def _mean_pooling(torch, output, attention_mask):
    token_embeddings = output[0]
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    summed = torch.sum(token_embeddings * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def _embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    torch, functional, tokenizer, model = _components()
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
    with torch.no_grad():
        output = model(**encoded)
    embeddings = _mean_pooling(torch, output, encoded["attention_mask"])
    embeddings = functional.normalize(embeddings, p=2, dim=1)
    return embeddings.cpu().numpy().astype("float32").tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    return _embed([text])[0]
