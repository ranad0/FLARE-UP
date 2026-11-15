"""Rebuild judged corpus from archived public NASA payloads and original files.

Only Microgravity / Reduced Gravity Combustion Science investigations are allowed.
Full report text is extracted separately; only explicitly reviewed passages enter
the judged corpus. Numbers come from experimental tables, never PDF inference.
"""
import csv, hashlib, html, io, json, math, pathlib, re, zipfile
from collections import Counter
from functools import lru_cache
from xml.etree import ElementTree
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'backend/data'
ALLOWED={'Microgravity Investigation','Reduced Gravity Investigation'}
def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',str(s or '')))).strip()
def digest(b): return hashlib.sha256(b).hexdigest()
@lru_cache(maxsize=None)
def file_digest(path): return digest(path.read_bytes())
def dump(path,obj): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def jsonl(path,rows): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf8')
def base(d,path,location,kind):
    return {'investigation_id':d['accession'],'investigation_label':d['accession'],'investigation_title':d['title'],'project_type':d['projectType'],'investigation_id_status':'verified','citation_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+d['accession'],'doi':d.get('doi') or None,'source_file':path.name,'source_relative_path':path.relative_to(DATA).as_posix(),'source_location':location,'source_sha256':file_digest(path),'source_record_type':kind,'content_type':kind,'retrieved_date':'2026-11-15','schema_version':'3.0','gravity_scope':'Microgravity investigation; individual row gravity not separately encoded by source'}
def chunk(b,text,**kwargs):
    text=clean(text)
    return {**b,**kwargs,'chunk_id':digest((b['source_relative_path']+b['source_location']+text).encode())[:24],'text':text,'embedding_text':b['investigation_title']+' '+text}
def split_text(text,size=1600):
    words=clean(text).split(); blocks=[]; current=[]; n=0
    for word in words:
        current.append(word); n+=len(word)+1
        if n>=size: blocks.append(' '.join(current)); current=[]; n=0
    if current: blocks.append(' '.join(current))
    return blocks
def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError): return None
def unit_from_header(header):
    h=header.strip()
    m=re.search(r'\((mg/s|mg/min|cm/s|mm|cm|bar|atm|K|C\s*|sec|minutes|percent|ppm)\)',h,re.I)
    if m: return m.group(1).strip()
    if ';' in h:
        tail=h.rsplit(';',1)[1].strip()
        if tail in ('mmHg','mm','s','mole fraction'): return tail
    if '% by vol' in h: return '% by vol'
    if '%' in h and 'O2' in h: return '%'
    return None
def ground_or_ambiguous_column(header):
    # PSI-99 mixes flight and ground columns; '?-g' is literally ambiguous in
    # the downloaded CSV, so do not silently repair its encoding to micro-g.
    return bool(re.search(r'(?:\b1[\s-]*g\b|normal\s*gravity|ground|\?[\s-]*g)',header,re.I))
def main():
    chunks=[]; numeric=[]; review=[]; table_chunks=[]; tables=[]; catalog=[]; excluded=[]; files=[]; excluded_columns=[]
    docs={}
    for path in sorted((DATA/'raw/psi').glob('PSI-*.json')):
        d=json.loads(path.read_text(encoding='utf8'))
        if d.get('projectType') not in ALLOWED or d.get('researchArea')!='Combustion Science':
            excluded.append({'id':d['accession'],'title':d.get('title'),'project_type':d.get('projectType'),'reason':'Ground investigation or outside Combustion Science','source_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+d['accession']}); continue
        docs[d['accession']]=d
        for field,typ in [('objective','research_objective'),('approach','experimental_approach'),('hypothesis','hypothesis_not_finding'),('description','investigation_description')]:
            if clean(d.get(field)):
                for i,text in enumerate(split_text(d[field])):
                    chunks.append(chunk(base(d,path,f'JSON field:{field}; segment:{i+1}',typ),text,evidence_role=typ))
        catalog.append({'id':d['accession'],'title':d['title'],'acronym':d.get('investigationAcronym'),'project_type':d['projectType'],'doi':d.get('doi') or None,'citation_url':'https://psi.nasa.gov/physci/repo/data/investigations/'+d['accession'],'summary':clean(d.get('objective'))[:400],'platform':d.get('flightProgram'),'identity_status':'verified','status':'partially_ingested','version':d.get('version')})
    ledger=json.loads((DATA/'meta/file_download_ledger.json').read_text())
    for item in ledger:
        if item['status']!='downloaded': files.append({**item,'ingestion_status':'download_failed'}); continue
        path=ROOT/item['local_path']; d=docs[item['investigation_id']]; ext=path.suffix.lower(); status='downloaded_not_parsed'; count=0; sparse_pages=[]
        if ext=='.csv':
            content=path.read_text(encoding='utf-8-sig',errors='replace')
            reader=csv.reader(io.StringIO(content)); headers=[h.strip() for h in next(reader)]
            omitted=[h for h in headers if ground_or_ambiguous_column(h)]
            if omitted: excluded_columns.append({'investigation_id':d['accession'],'source_file':path.name,'columns':omitted,'reason':'Explicit ground comparison or ambiguous gravity label; retained only in original source/provenance.'})
            rows=0; values=0
            for rowno,raw in enumerate(reader,2):
                if not any(s.strip() for s in raw): continue
                row=dict(zip(headers,raw)); rows+=1
                b=base(d,path,f'row:{rowno}','experimental_table')
                b.update(source_row_number=rowno,conditions={k:v for k,v in row.items() if v.strip() and k not in omitted},units={h:unit_from_header(h) for h in headers if h not in omitted},evidence_role='experimental_table_row')
                table_chunks.append(chunk(b,'; '.join(f'{k}: {v}' for k,v in row.items() if v.strip()),judged_eligible=False,row_caveat='Original row for audit only; may contain ground comparison columns. Numeric retrieval uses only permitted columns.'))
                for header,value in row.items():
                    if header in omitted: continue
                    if not value.strip(): continue
                    unit=unit_from_header(header); n=number(value)
                    # Preserve inline dimensions without converting them or expanding ranges.
                    m=re.fullmatch(r'\s*([+-]?(?:\d*\.)?\d+)\s*(cm/s|cm|mm|atm|bar)\s*',value)
                    if m: n=float(m.group(1)); unit=m.group(2)
                    if n is None: continue
                    # IDs, dates, settings and counts are not physical observations.
                    if not unit and not re.search(r'^(X[Of]|XO2|Xfuel|XC2H4|Xf|Zst|mean Zst|Oxygen|Nitrogen|Helium)',header): continue
                    flags=[] if unit else ['unit_not_explicit_in_source_header']
                    if header=='Burning rate; mm': flags.append('source_unit_dimension_requires_review_do_not_correct')
                    pressure=None
                    for key in ('pmean (atm)','Ambient Pressure (atm)'):
                        pressure=number(row.get(key))
                        if pressure is not None: break
                    r={**b,'record_type':'numeric_observation','record_id':digest((path.name+str(rowno)+header).encode())[:24],'quantity_name':header,'variable':header,'value':n,'value_raw':value,'unit':unit,'unit_status':'explicit_in_source' if unit else 'unknown','quality_flags':flags,'source_column_name':header,'source_row_values':row,'series_type':'experiment','series_type_basis':'official_experimental_table','pressure_atm':pressure,'record_status':'source_transcribed','dataset_id':digest(path.name.encode())[:16]}
                    numeric.append(r); values+=1
            tables.append({'investigation_id':d['accession'],'source_file':path.name,'rows':rows,'numeric_records':values,'headers':headers,'sha256':digest(path.read_bytes())})
            status='fully_transcribed_table'; count=rows
        elif ext=='.pdf':
            from pypdf import PdfReader
            try:
                reader=PdfReader(path); pages=[]
                for no,page in enumerate(reader.pages,1):
                    text=page.extract_text() or ''; pages.append(text)
                    if len(clean(text))<60: sparse_pages.append(no); continue
                    for i,block in enumerate(split_text(text)):
                        review.append(chunk(base(d,path,f'PDF page:{no}; segment:{i+1}','report_text_needs_scope_review'),block,judged_eligible=False,review_reason='Report may mix flight, ground, modeling, plans and results; passage scope not reviewed.'))
                count=len(pages); status='text_extracted_pending_scope_review'
                # These passages were read in context; avoid the ground experiment abstract
                # immediately following the ISS abstract on CFI-G report page 23.
                selected=[]
                if d['accession']=='PSI-159' and 'FinalRpt' in path.name:
                    text=pages[22]; start=text.index('Abstract for Spherical'); end=text.index('Abstract for Cool Diffusion')
                    selected=[(23,text[start:end],'preliminary_flight_results')]
                if d['accession']=='PSI-39' and 'Final' in path.name:
                    text=pages[2]; start=text.index('1.  Overview'); end=text.index('2.  Introduction')
                    selected=[(3,text[start:end],'flight_science_overview'),(5,pages[4],'flight_science_background'),(6,pages[5],'flight_operations_and_observations')]
                if d['accession']=='PSI-102' and 'Final' in path.name:
                    selected=[(3,pages[2],'flight_report_abstract'),(4,pages[3],'flight_report_abstract_continued')]
                if d['accession']=='PSI-25' and 'Summary Report' in path.name:
                    # Read in context: these sections explicitly describe ISS
                    # experiments, retaining material and flow-regime scope.
                    t=pages[26]; a=t.index('2.2.1 Abstract'); z=t.index('Symbols',a)
                    t2=pages[100]; a2=t2.index('7.1.1 Abstract'); z2=t2.index('7.1.2 Introduction',a2)
                    selected=[(27,t[a:z],'flight_report_opposed_flow_abstract'),(101,t2[a2:z2],'flight_report_concurrent_flow_abstract')]
                if d['accession']=='PSI-10' and 'FinalRpt' in path.name:
                    selected=[(25,pages[24],'preliminary_flight_results_and_model_comparison'),(26,pages[25].split('Publications:')[0],'preliminary_flight_results_and_model_comparison')]
                    selected.append((27,pages[26][pages[26].index('5. Follow-On Experiments'):],'flight_experiment_limitations'))
                if d['accession']=='PSI-23' and 'final_report' in path.name:
                    selected=[(no,pages[no-1],'preliminary_flight_results_and_interpretation') for no in range(26,31)]
                    selected.append((25,pages[24],'flight_research_goals_and_test_matrix'))
                if d['accession']=='PSI-101' and 'Final Report' in path.name:
                    t=pages[2]; selected=[(3,t[t.index('Flight Operation'):],'flight_operations')]
                    t=pages[3]; selected.append((4,t[t.index('SAMER results'):t.index('A. Moment Instrument Results')],'preliminary_flight_results'))
                if d['accession']=='PSI-107' and path.name.endswith('SPICE_FinalReport.pdf'):
                    # This draft has inconsistent smoke-point totals (52 vs55)
                    # and fuel ranking elsewhere; omit those portions.
                    t=pages[18]; selected=[(19,t[t.index('SPICE FLIGHT TESTS'):t.index('0 co-flow')],'flight_measurement_method')]
                    t=pages[19]; selected.append((20,t[:t.index('Table 1. Summary')],'flight_results_and_measurement_limitations'))
                    selected.append((21,pages[20].split('Figure 17. Still camera')[0],'flight_results_coflow_and_soot'))
                if d['accession']=='PSI-39' and 'Final' in path.name:
                    selected.extend([(9,pages[8],'preliminary_flight_results'),(10,pages[9],'preliminary_flight_results')])
                if d['accession']=='PSI-102' and 'Final' in path.name:
                    t=pages[24]; selected.append((25,t[t.index('5.  Test Results and Discussions'):],'flight_results_and_detector_response'))
                    t=pages[28]; selected.append((29,t[t.index('6.  Closing Remarks'):],'flight_report_conclusion'))
                for no,text,role in selected:
                    for i,block in enumerate(split_text(text)):
                        chunks.append(chunk(base(d,path,f'PDF page:{no}; reviewed segment:{i+1}',role),block,evidence_role=role,gravity_scope='ISS flight experiment; context may explicitly compare Earth',scope_review='passage_read_in_context_2026-11-15'))
            except Exception as e: status='extraction_failed_'+type(e).__name__
        elif ext=='.docx':
            with zipfile.ZipFile(path) as z:
                root=ElementTree.fromstring(z.read('word/document.xml'))
                text=' '.join(x.text or '' for x in root.iter() if x.tag.endswith('}t'))
            for i,block in enumerate(split_text(text)):
                review.append(chunk(base(d,path,f'DOCX text segment:{i+1}','readme_pending_review'),block,judged_eligible=False))
            count=len(text); status='full_text_extracted_pending_scope_review'
        files.append({**item,'ingestion_status':status,'extracted_pages_or_rows_or_characters':count,'sparse_or_image_pages_not_ocrd':sparse_pages})
    counts=Counter(c['investigation_id'] for c in chunks); nc=Counter(r['investigation_id'] for r in numeric)
    for item in catalog:
        item.update(text_chunks=counts[item['id']],structured_records=nc[item['id']],fuels=sorted({str(r['conditions'].get('Fuel')) for r in numeric if r['investigation_id']==item['id'] and r['conditions'].get('Fuel')}),top_variables=[k for k,_ in Counter(r['quantity_name'] for r in numeric if r['investigation_id']==item['id']).most_common(8)])
    jsonl(DATA/'chunks.jsonl',chunks)
    jsonl(DATA/'structured/nasa_observations.jsonl',numeric)
    jsonl(DATA/'review/report_chunks_pending_review.jsonl',review)
    jsonl(DATA/'review/table_rows_audit_only.jsonl',table_chunks)
    dump(DATA/'meta/catalog.json',catalog)
    report={'built_date':'2026-11-15','policy':'Microgravity/Reduced Gravity Combustion Science only. Ground investigations excluded. Full reports retained separately until passage-level review. No PDF-derived numeric claims. Unknown units remain null.','eligible_investigations':len(catalog),'excluded_investigations':excluded,'text_chunks':len(chunks),'structured_records':len(numeric),'pending_review_chunks':len(review),'downloaded_bytes':sum(f.get('bytes',0) for f in files),'downloaded_files':sum(f['status']=='downloaded' for f in files),'experimental_tables':len(tables),'experimental_table_rows':sum(t['rows'] for t in tables),'numeric_records_with_unknown_units':sum(r['unit'] is None for r in numeric),'numeric_records_with_quality_flags':sum(bool(r['quality_flags']) for r in numeric),'tables':tables,'files':files,'limitations':['Experimental tables contain conditions and summaries as well as observations; a numeric cell is not automatically a measured outcome.','Empty cells and non-scalar ranges are not expanded or imputed.','Raw videos/images and unrestricted multi-terabyte experiment collections are cataloged in NASA manifests but not downloaded.','Some reports mix flight and ground studies. Only explicitly selected reviewed passages enter judged text retrieval.','Two legacy DOC files retained without text extraction.','Sparse and image-only PDF pages are listed individually and were not OCRd.','No reduced-gravity-only investigations were returned by this combustion search; accepted investigations are Microgravity.']}
    report.update(table_rows_audit_only=len(table_chunks),excluded_columns=excluded_columns,
                  reviewed_report_passages=[{'investigation_id':c['investigation_id'],'source_file':c['source_file'],'source_location':c['source_location'],'evidence_role':c.get('evidence_role')} for c in chunks if c['source_file'].endswith('.pdf')])
    dump(DATA/'meta/ingestion_report.json',report)
    print(json.dumps({k:report[k] for k in ('eligible_investigations','text_chunks','structured_records','pending_review_chunks')}))
if __name__=='__main__': main()
