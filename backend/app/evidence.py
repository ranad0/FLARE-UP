"""Local retrieval and evidence assembly, followed by optional grounded synthesis."""
import json, re, os, hashlib
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from app.config import CHUNKS_PATH, TOP_K, DATA_META_DIR, LOCAL_VECTOR_INDEX
from app.structured_data import search_structured
from app.router import route_question
from app.query_language import expand_query

ALLOWED = {'Microgravity Investigation', 'Reduced Gravity Investigation'}

@lru_cache(maxsize=1)
def chunks():
    return tuple(r for line in CHUNKS_PATH.read_text(encoding='utf8').splitlines() if line.strip()
                 if (r := json.loads(line)).get('project_type') in ALLOWED)

@lru_cache(maxsize=1)
def index():
    vectorizer=TfidfVectorizer(stop_words='english',ngram_range=(1,2),sublinear_tf=True,max_features=40000)
    matrix=vectorizer.fit_transform([r.get('text','') for r in chunks()])
    svd=TruncatedSVD(n_components=max(1,min(96,matrix.shape[0]-1,matrix.shape[1]-1)),random_state=42)
    return vectorizer,matrix,svd,normalize(svd.fit_transform(matrix))

def _local_search(question,limit=None):
    if not chunks(): return []
    # Curated topic translation preserves English scientific source wording.
    question=expand_query(question)
    vec,matrix,svd,latent=index()
    query=vec.transform([question])
    if query.nnz==0: return []
    lexical=(matrix@query.T).toarray().ravel()
    semantic=(latent@normalize(svd.transform(query)).T).ravel()
    scores=.65*lexical+.35*np.maximum(semantic,0)
    explicit=re.search(r'\bPSI-\d+\b',question,re.I)
    out=[]
    for i in np.argsort(-scores):
        row=chunks()[int(i)]
        if scores[i]<.12 or lexical[i]<.025: continue
        if explicit and row.get('investigation_id')!=explicit.group().upper(): continue
        out.append({**row,'score':round(float(scores[i]),5),'retrieval_method':'local-lsa-tfidf',
                    'title':row.get('investigation_title',row.get('investigation_id')),
                    'url':row.get('citation_url'),'excerpt':row.get('text')})
        if len(out)>=(limit or TOP_K): break
    return out

def search_text(question,limit=None):
    fallback=_local_search(question,limit)
    if os.getenv('RETRIEVAL_MODE','local')!='minilm': return fallback
    try:
        manifest=json.loads(LOCAL_VECTOR_INDEX.with_suffix('.manifest.json').read_text())
        if manifest['corpus_sha256']!=hashlib.sha256(CHUNKS_PATH.read_bytes()).hexdigest(): raise ValueError('Stale index')
        from app.embedder import embed_query
        from app.vector_store import search_chunks
        active={r['chunk_id']:r for r in chunks()}
        hits=search_chunks(embed_query(question),limit=(limit or TOP_K)*2)
        semantic=[]
        explicit=re.search(r'PSI-\d+',question,re.I)
        for hit in hits:
            r=active.get(hit.payload.get('chunk_id'))
            if not r or hit.score<.25 or (explicit and r['investigation_id']!=explicit.group().upper()): continue
            semantic.append({**r,'score':hit.score,'retrieval_method':'minilm-cosine',
                'title':r.get('investigation_title'),'url':r.get('citation_url'),'excerpt':r.get('text')})
        # Preserve hybrid vector / lexical retrieval with reciprocal rank fusion.
        merged={};scores={}
        for weight,rows in ((1,semantic),(.72,fallback)):
            for rank,row in enumerate(rows,1):
                key=row['chunk_id'];merged.setdefault(key,row);scores[key]=scores.get(key,0)+weight/(50+rank)
        return [merged[k] for k in sorted(scores,key=scores.get,reverse=True)[:limit or TOP_K]]
    except (ImportError,OSError,ValueError,KeyError,RuntimeError):
        return [{**r,'retrieval_warning':'MiniLM unavailable or stale; explicit local LSA fallback.'} for r in fallback]

def ask_flare_up(question):
    decision=route_question(question); route=decision['route']
    sources=search_text(question) if route in {'text','hybrid'} else []
    structured=search_structured(question) if route in {'structured','hybrid'} else {'parsed':{},'results':[]}
    records=structured['results']; parts=[]
    if records:
        parts.append('Retrieved source records (not predictions):')
        for i,r in enumerate(records[:6],1):
            parts.append(f"[{i}] {r.get('investigation_id',r.get('investigation',''))} · {r.get('quantity_name',r.get('facet','value'))}: {r.get('value')} {r.get('unit') or '(unit not stated)'} — {r.get('source_file','')} · {r.get('source_location','')}")
    elif route in {'structured','hybrid'}:
        parts.append('No validated numeric record matches this request in the judged corpus. No value or unit has been inferred.')
    if sources:
        parts.append('Relevant source passages follow. Objectives and hypotheses describe research intent, not established findings.')
        for i,s in enumerate(sources[:3],1):
            text=s['text']
            if len(text)>1000: text=text[:1000].rsplit(' ',1)[0]+' […]'
            parts.append(f"[T{i}] {s.get('investigation_id')} · {s.get('source_location','')}\n{text}")
    elif route in {'text','hybrid'}:
        parts.append('No sufficiently relevant passage was found. Try naming a fuel, investigation, smoke, flame spread, or extinction.')
    flags=sorted({str(flag) for r in records for flag in r.get('quality_flags',[])})
    if flags: parts.append('Source quality notes: '+ '; '.join(flags))
    if 'dext' in question.lower() or 'psi-117' in question.lower():
        parts.append('The supplied PSI-117 comparison is excluded: NASA classifies that investigation as Ground Investigation. It is retained only in the legacy regression fixture.')
    from app.synthesis import synthesize, render_answer
    summary=synthesize(question,route,sources,records)
    return {'question':question,'route':route,'routing_reason':decision['reason'],'answer':render_answer(summary),
            'extractive_evidence':'\n\n'.join(parts),'synthesis':summary,
            'llm_status':summary['status'],'sources':sources,'structured_query':structured['parsed'],
            'structured_results':records,'structured_total':structured.get('total_matches',len(records)),
            'notes':['Retrieval: '+', '.join(sorted({s.get('retrieval_method','unknown') for s in sources})),'Summary mode: '+summary['status']+'. Numerical values are rendered from structured records only.',structured.get('warning',''),
                     'Unknown units remain unknown. Ground investigations are excluded.']}

def investigations_catalog():
    data=json.loads((DATA_META_DIR/'catalog.json').read_text(encoding='utf8'))
    return data if isinstance(data,list) else data.get('investigations',[])

def retrieval_stats():
    return {'chunk_count':len(chunks()),'method':os.getenv('RETRIEVAL_MODE','local'),'generation':'Groq grounded synthesis with extractive fallback' if os.getenv('GROQ_API_KEY') else 'extractive fallback; Groq key not configured',
            'corpus':'microgravity / reduced-gravity only'}
