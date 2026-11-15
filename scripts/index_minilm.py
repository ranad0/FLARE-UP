"""Rebuild the original MiniLM/local JSON vector index for the judged corpus."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.embedder import embed_documents
from app.vector_store import reset_collection,add_chunks
from app.config import CHUNKS_PATH,LOCAL_VECTOR_INDEX
rows=[json.loads(l) for l in CHUNKS_PATH.read_text(encoding='utf8').splitlines() if l.strip()]
rows=[r for r in rows if r.get('project_type') in {'Microgravity Investigation','Reduced Gravity Investigation'}]
first=embed_documents([rows[0]['text']])[0]
reset_collection(len(first))
for start in range(0,len(rows),12):
    batch=rows[start:start+12]
    add_chunks(batch,embed_documents([r['text'] for r in batch]))
    print('Indexed',min(start+12,len(rows)),'/',len(rows),flush=True)
manifest={'corpus_sha256':hashlib.sha256(CHUNKS_PATH.read_bytes()).hexdigest(),'model':'sentence-transformers/all-MiniLM-L6-v2'}
LOCAL_VECTOR_INDEX.with_suffix('.manifest.json').write_text(json.dumps(manifest),encoding='utf8')
