"""Download public PSI metadata; keep original payloads and an explicit selection ledger."""
import concurrent.futures, json, pathlib, urllib.request, urllib.parse, hashlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / 'backend/data/raw/psi'
RAW.mkdir(parents=True, exist_ok=True)
BASE = 'https://psi.nasa.gov/geode-py/ws/repo/'
def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()
def main():
    url = BASE + 'search?' + urllib.parse.urlencode(dict(term='combustion', source='psi', type='investigation', size=200, **{'from':0}))
    data=fetch(url); (RAW/'search.json').write_bytes(data)
    hits=json.loads(data)['hits']['hits']
    print('Search hits',len(hits),flush=True)
    def one(hit):
        src=hit['_source']; accession=src['Accession']
        try:
            body=fetch(BASE+'investigations/'+accession)
            payload=json.loads(body)
            (RAW/(accession+'.json')).write_bytes(body)
            return {'id':accession,'title':payload.get('title'),'project_type':payload.get('projectType'),'research_area':payload.get('researchArea'),'sha256':hashlib.sha256(body).hexdigest(),'source_url':BASE+'investigations/'+accession,'status':'metadata_downloaded'}
        except Exception as e:
            return {'id':accession,'status':'failed','error':str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(one,hits))
    (ROOT/'backend/data/meta/download_ledger.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    for r in results: print(r['id'],r.get('project_type'),r['status'],flush=True)
if __name__=='__main__': main()
