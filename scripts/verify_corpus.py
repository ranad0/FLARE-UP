"""Integrity and scope checks against original NASA tables, without network access."""
import csv, hashlib, io, json, pathlib
import re
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'backend/data'
def rows(path): return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()]
def main():
    records=rows(DATA/'structured/nasa_observations.jsonl'); chunks=rows(DATA/'chunks.jsonl')
    allowed={x['id'] for x in json.loads((DATA/'meta/catalog.json').read_text(encoding='utf8'))}
    assert len({x['record_id'] for x in records})==len(records),'Duplicate record IDs'
    assert len({x['chunk_id'] for x in chunks})==len(chunks),'Duplicate chunk IDs'
    cache={}
    for row in records+chunks:
        assert row['investigation_id'] in allowed
        assert row['project_type'] in {'Microgravity Investigation','Reduced Gravity Investigation'}
        path=DATA/row['source_relative_path']; assert path.is_file()
        if path not in cache: cache[path]=hashlib.sha256(path.read_bytes()).hexdigest()
        assert cache[path]==row['source_sha256'],'Source changed after ingestion'
        assert row['citation_url'].startswith('https://psi.nasa.gov/physci/repo/data/investigations/')
    tables={}
    for row in records:
        assert not re.search(r'(?:\b1[\s-]*g\b|normal\s*gravity|ground|\?[\s-]*g)',row['quantity_name'],re.I),'Non-flight gravity column entered judged numeric corpus'
        assert not any(re.search(r'(?:\b1[\s-]*g\b|normal\s*gravity|ground|\?[\s-]*g)',key,re.I) for key in row['conditions']),'Non-flight comparison entered conditions'
        path=DATA/row['source_relative_path']
        if path not in tables:
            reader=csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig',errors='replace')))
            header=[s.strip() for s in next(reader)]
            tables[path]={i:dict(zip(header,values)) for i,values in enumerate(reader,2)}
        assert tables[path][row['source_row_number']][row['source_column_name']]==row['value_raw']
    assert not any(x['investigation_id']=='PSI-117' for x in records+chunks)
    assert not any(x['source_record_type']=='experimental_table' for x in chunks),'Table rows must not flood descriptive retrieval'
    print(f'PASS: {len(chunks)} chunks, {len(records)} numeric cells; scope, hashes, IDs and original CSV values verified.')
    supplemental=DATA/'supplemental/chunks.jsonl'
    if supplemental.exists():
        context=rows(supplemental)
        for c in context:
            assert c['source_class']=='contextual_resource' and c['judged_eligible'] is False
            assert c['investigation_id'] is None
            path=DATA/'supplemental/raw'/c['source_file']
            if path not in cache: cache[path]=hashlib.sha256(path.read_bytes()).hexdigest()
            assert cache[path]==c['source_sha256']
        assert not {c['chunk_id'] for c in context}&{c['chunk_id'] for c in chunks}
        print(f'PASS: {len(context)} supporting chunks remain separate; source hashes verified.')
if __name__=='__main__': main()
