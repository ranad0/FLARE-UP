"""Explicit 2.0.0 → 3.0 compatibility adapter, applied after the base build.

This consumes the teammate pipeline outputs; it does not extract new measurements.
Only the audited record IDs and literal reviewed passage are admissible.
"""
import csv,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'backend/data';HANDOFF=ROOT/'data_handoffs/handoff_3'
def read(p): return [json.loads(l) for l in p.read_text(encoding='utf8').splitlines() if l.strip()]
def dump(p,data):p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
def write(p,rows):p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r):return r['source_sha256'],r.get('source_row_number'),r.get('source_column_name')
def main():
    decisions=json.loads((HANDOFF/'review_decisions.json').read_text())
    numeric=read(DATA/'structured/nasa_observations.jsonl'); active={key(r):r for r in numeric}
    incoming=read(next((HANDOFF/'data/processed/structured').glob('PSI-98*')))
    approved=set(decisions['approved_numeric']);added=0
    metadata=json.loads((DATA/'raw/psi/PSI-98.json').read_text())
    assert metadata['researchArea']=='Combustion Science' and metadata['projectType']=='Microgravity Investigation'
    for original in incoming:
        if original['record_id'] not in approved:continue
        assert original['schema_version']=='2.0.0' and original['investigation_id']=='PSI-98'
        prior=active.get(key(original))
        if prior:
            assert all(prior.get(f)==original.get(f) for f in ('value','value_raw','unit'))
            continue
        candidates=[p for p in (DATA/'raw').rglob('*.csv') if sha(p)==original['source_sha256']]
        assert candidates,'Missing immutable original'
        source=sorted(candidates)[0]
        with source.open(encoding='utf-8-sig',newline='') as f:
            table=list(csv.reader(f));headers=[h.strip() for h in table[0]]
        value=table[original['source_row_number']-1][headers.index(original['source_column_name'])]
        assert value==original['value_raw'] and float(value)==original['value']
        assert original['source_column_name'] in {'Ignition Power (W)','Ignition Time (s)','Burn Time (s)'}
        assert original['unit']==original['source_column_name'].split('(')[-1].strip(')')
        migrated={**original,'schema_version':'3.0','project_type':metadata['projectType'],
            'investigation_title':metadata['title'],'research_area':metadata['researchArea'],
            'source_relative_path':source.relative_to(DATA).as_posix(),'doi':metadata['doi'],
            'series_type_basis':'official_experimental_table','evidence_role':'experimental_table_row',
            'gravity_scope':'Microgravity investigation; individual row gravity not separately encoded by source',
            'migration':{'adapter':decisions['adapter_version'],'original_schema_version':'2.0.0',
                'original_record':original,'eligibility_basis':'raw/psi/PSI-98.json',
                'doi_basis':'raw/psi/PSI-98.json','series_basis':'Same NASA experimental table SHA-256 already approved in base corpus'}}
        numeric.append(migrated);active[key(migrated)]=migrated;added+=1
    passages=read(DATA/'chunks.jsonl');ids={c['chunk_id'] for c in passages}
    new_files=[]
    for p in decisions['reviewed_passages']:
        m=json.loads((DATA/'raw/psi'/f"{p['investigation_id']}.json").read_text())
        assert m['researchArea']=='Combustion Science' and m['projectType']=='Microgravity Investigation'
        source=HANDOFF/'data/raw'/p['investigation_id']/p['source_file']
        assert sha(source)==p['source_sha256']
        target=DATA/'raw/handoff_3'/p['source_file'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        cid=hashlib.sha256((p['source_sha256']+p['source_location']+p['text']).encode()).hexdigest()[:24]
        if cid not in ids:
            passages.append({**p,'schema_version':'3.0','chunk_id':cid,'embedding_text':m['title']+' '+p['text'],
              'investigation_title':m['title'],'investigation_id_status':'verified','project_type':m['projectType'],
              'research_area':m['researchArea'],'citation_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+m['accession'],
              'doi':m['doi'],'content_type':'research_objective','source_record_type':'reviewed_design_document',
              'source_relative_path':target.relative_to(DATA).as_posix(),'scope_review':p['review_note'],
              'gravity_scope':'Historical SAME design, archived under SAME-R; not measured reflight findings',
              'migration':{'adapter':decisions['adapter_version'],'handoff_source':'data_handoffs/handoff_3/review_decisions.json'}})
        new_files.append({'investigation_id':m['accession'],'local_path':target.relative_to(ROOT).as_posix(),'bytes':target.stat().st_size,'sha256':sha(target),'status':'downloaded','acquisition':'data-team handoff; official resource name checked against archived PSI payload','ingestion_status':'one_reviewed_objective_other_passages_pending','source_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+m['accession']})
    write(DATA/'structured/nasa_observations.jsonl',numeric);write(DATA/'chunks.jsonl',passages)
    catalog=json.loads((DATA/'meta/catalog.json').read_text())
    for c in catalog:
        c['text_chunks']=sum(r['investigation_id']==c['id'] for r in passages)
        c['structured_records']=sum(r['investigation_id']==c['id'] for r in numeric)
    dump(DATA/'meta/catalog.json',catalog)
    report=json.loads((DATA/'meta/ingestion_report.json').read_text())
    paths={f['local_path'] for f in report['files']}
    report['files'] += [f for f in new_files if f['local_path'] not in paths]
    for table in report['tables']:
        table['numeric_records']=sum(r['source_sha256']==table['sha256'] for r in numeric)
    report.update(text_chunks=len(passages),structured_records=len(numeric),
        downloaded_files=sum(f['status']=='downloaded' for f in report['files']),
        downloaded_bytes=sum(f.get('bytes',0) for f in report['files']))
    report['handoff_3']={'audit':'data_handoffs/handoff_3/audit_report.json','adapter':decisions['adapter_version'],
       'approved_scalar_records':len(approved),'reviewed_text_additions':len(decisions['reviewed_passages']),
       'new_investigations':0,'review_collection':'data_handoffs/handoff_3/data/processed',
       'scope':'One historical design objective, not a measured result; six exact CSV scalars. Other extraction pending.'}
    dump(DATA/'meta/ingestion_report.json',report)
    print(json.dumps({'new_scalars_this_run':added,'scalar_total':len(numeric),'text_total':len(passages)}))
if __name__=='__main__':main()
