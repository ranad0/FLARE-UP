"""Fetch selected public PSI science documents; never follow restricted files."""
import concurrent.futures, hashlib, json, pathlib, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
RAW=ROOT/'backend/data/raw/psi'
OUT=ROOT/'backend/data/raw/downloads'
def eligible(d):
    return d.get('projectType') in ('Microgravity Investigation','Reduced Gravity Investigation') and d.get('researchArea')=='Combustion Science'
def main():
    candidates=[]
    for path in RAW.glob('PSI-*.json'):
        d=json.loads(path.read_text(encoding='utf8'))
        if not eligible(d): continue
        seen=set()
        for f in d.get('added',[])+d.get('experimentalTable',[])+d.get('readme',[]):
            name=f.get('file_name',''); lower=name.lower()
            if name in seen: continue
            seen.add(name)
            if f.get('restricted') or f.get('visible') is False: continue
            select=('experimental table' in lower or 'reports_' in lower or 'readme' in lower or 'read me' in lower or 'faq' in lower)
            if select and pathlib.Path(name).suffix.lower() in ('.csv','.pdf','.docx','.txt','.xlsx','.doc') and float(f.get('file_size') or 0)<60_000_000:
                candidates.append((d,f))
    def one(pair):
        d,f=pair; accession=d['accession']; name=f['file_name']; dest=OUT/accession/name; dest.parent.mkdir(parents=True,exist_ok=True)
        row={'investigation_id':accession,'source_file':name,'project_type':d['projectType'],'source_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+accession,'api_url':'https://psi.nasa.gov/geode-py/ws/studies/'+accession+'/download','file_version':f.get('version',1),'study_version':d['version'],'source_subcategory':f.get('subcategory',''),'local_path':str(dest.relative_to(ROOT)).replace('\\','/')}
        try:
            if not dest.exists():
                params=urllib.parse.urlencode({'file':name,'version':f.get('version',1),'studyVersion':d['version'],'redirect':'false'})
                with urllib.request.urlopen(row['api_url']+'?'+params,timeout=45) as r: signed=r.read().decode().strip().strip('"')
                with urllib.request.urlopen(signed,timeout=90) as r: body=r.read()
                dest.write_bytes(body)
            body=dest.read_bytes(); row.update(status='downloaded',bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        except Exception as e: row.update(status='failed',error=type(e).__name__)
        print(accession,name,row['status'],flush=True)
        return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(one,candidates))
    (ROOT/'backend/data/meta/file_download_ledger.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print('Downloaded',sum(r['status']=='downloaded' for r in results),'of',len(results),flush=True)
if __name__=='__main__': main()
