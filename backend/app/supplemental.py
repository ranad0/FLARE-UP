"""Separate search over NASA challenge context; never part of judged retrieval."""
import json
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from app.config import BACKEND_ROOT

ROOT = BACKEND_ROOT / 'data' / 'supplemental'

def resource_catalog():
    return json.loads((ROOT / 'resource_catalog.json').read_text(encoding='utf8'))

@lru_cache(maxsize=1)
def context_index():
    rows = [json.loads(line) for line in (ROOT / 'chunks.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    assert all(r.get('judged_eligible') is False for r in rows)
    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2), sublinear_tf=True)
    return rows, vectorizer, vectorizer.fit_transform([r['text'] for r in rows])

def search_context(question, limit=6):
    rows, vectorizer, matrix = context_index()
    scores = (matrix @ vectorizer.transform([question]).T).toarray().ravel()
    return [{**rows[int(i)], 'score':round(float(scores[i]), 5)}
            for i in scores.argsort()[::-1][:limit] if scores[i] >= .055]
