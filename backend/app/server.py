import json
from pathlib import Path
from typing import Literal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.config import ALLOWED_ORIGINS, DATA_META_DIR
from app.rag import ask_flare_up
from app.retrieval import search_text
from app.router import route_question
from app.catalog import investigations_catalog
from app.evidence import retrieval_stats
from app.structured_data import search_structured, structured_stats, load_structured_records, _record_pressure_bar
from app.supplemental import resource_catalog, search_context

app=FastAPI(title='FLARE UP Evidence Engine',version='2.0.0')
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

class AskRequest(BaseModel):
    question:str=Field(min_length=3,max_length=2500)

class ScenarioRequest(BaseModel):
    gravity:Literal['earth','microgravity']='microgravity'
    oxygen_percent:float=Field(default=21,ge=15,le=40)
    pressure_psi:float=Field(default=14.7,ge=4.3,le=14.7)
    airflow:float=Field(default=.5,ge=0,le=3)
    airflow_direction_degrees:float=Field(default=0,ge=0,le=360)
    sample_type:Literal['Gaseous fuel','Liquid fuel','Fabric','Polymer','gaseous fuel','liquid fuel','fabric','polymer']='Gaseous fuel'

@app.get('/health')
def health(): return {'status':'ok','retrieval':retrieval_stats(),'structured_records':structured_stats()['record_count'],'paid_dependencies':False}
@app.get('/stats')
def stats(): return {'vector':retrieval_stats(),'structured':structured_stats(),'investigations':investigations_catalog()}
@app.get('/investigations')
def investigations(): return {'investigations':investigations_catalog()}
@app.get('/provenance')
def provenance(): return json.loads((DATA_META_DIR/'ingestion_report.json').read_text(encoding='utf8'))
@app.post('/route')
def route(r:AskRequest): return route_question(r.question)
@app.post('/ask')
def ask(r:AskRequest): return ask_flare_up(r.question.strip())
@app.post('/search')
def search(r:AskRequest): return {'results':search_text(r.question)}
@app.post('/structured-search')
def structured(r:AskRequest): return search_structured(r.question)

@app.get('/resources')
def resources(): return {'resources':resource_catalog(),'scope':'NASA challenge context; separate from judged investigations'}
@app.post('/resources/search')
def resources_search(r:AskRequest): return {'results':search_context(r.question),'scope':'contextual_resource','judged_eligible':False}

@app.post('/scenario/analyze')
def scenario(r:ScenarioRequest):
    # Only gaseous-fuel microgravity records can be compared with CFI-G.
    # Pressure is comparable; oxygen fractions need source-specific interpretation.
    matches=[]
    if r.gravity=='microgravity' and r.sample_type.lower()=='gaseous fuel':
        for row in load_structured_records():
            if row.get('investigation_id')!='PSI-159' or 'burn time' not in str(row.get('quantity_name','')).lower(): continue
            p=_record_pressure_bar(row)
            if p is None: continue
            psi=p*14.5037738
            matches.append({'investigation':'PSI-159','title':'ACME CFI-G','pressure_psi':round(psi,4),
                'conditions':row.get('source_row_values',row.get('conditions',{})),
                'reported_values':{str(row['quantity_name']):row.get('value')},
                'source':f"{row.get('source_file')} · {row.get('source_location')}",
                'url':row.get('citation_url'),'doi':row.get('doi'),'pressure_difference_psi':abs(psi-r.pressure_psi),
                'match_basis':'Pressure only; fuel composition, oxygen, geometry and airflow are not matched.'})
        matches=sorted(matches,key=lambda x:x['pressure_difference_psi'])[:3]
    topic={'gaseous fuel':'spherical cool diffusion flames','liquid fuel':'FLEX droplet extinction',
           'fabric':'BASS fabric flame spread ventilation','polymer':'BASS PMMA flame spread'}[r.sample_type.lower()]
    sources=search_text(topic,4)
    related=list(dict.fromkeys(s.get('investigation_id') for s in sources if s.get('investigation_id')))
    summary=('Related NASA research and pressure-comparable records found. The full combination of conditions is not matched.' if matches else
        'Related NASA research found for this material topic. The full combination of conditions is not matched.' if sources else
        'No related passage was found in the reviewed corpus for this material topic.')
    return {'scenario':r.model_dump(),'evidence_match':{'level':'partial' if matches else 'context only','limited':True,'exact_match':False,
        'summary':summary,'related_passages':len(sources),'related_investigations':related,
        'matching_scope':'Gaseous fuel category and nearest reported pressure only.' if matches else 'Material-topic relevance only; experimental conditions are not matched.'},'closest_records':matches,
        'visual_state':{'illustrative':True,'gravity':r.gravity,'airflow':r.airflow,'oxygen_percent':r.oxygen_percent},
        'analysis':{'closest_investigation':'PSI-159 · ACME CFI-G' if matches else None,
            'reported_by_sources':[{'investigation':s.get('investigation_id'),'source':s.get('source_file'),
            'location':s.get('source_location'),'evidence_type':s.get('content_type'),'passage':s.get('text')} for s in sources],
            'interpretation':('These sources provide research context. Nearby pressure records are not a validated prediction for the chosen scenario.' if matches else 'These studies concern the selected material topic. They do not establish how the combined oxygen, pressure and airflow settings would behave.'),
            'not_established':['Direct evidence for this exact scenario is not available.',
                'Ignition, extinction, temperature and burn rate for these combined inputs.',
                'A numeric mapping from the illustrative airflow control to measured ventilation.',
                'A universal flame colour or shape for every material in microgravity.'], 'limited_evidence':True},
        'sources':sources,'scientific_disclaimer':'Evidence-informed visualization — not a numerical combustion simulation.'}

frontend=Path(__file__).resolve().parents[2]/'frontend/dist'
if frontend.exists(): app.mount('/',StaticFiles(directory=frontend,html=True),name='frontend')
