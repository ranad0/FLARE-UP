"""Real HTTP integration tests; start server on 8010 first."""
import json,urllib.request,urllib.error,sys
base='http://127.0.0.1:8010'

def call(path,payload=None):
    request=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as r:return r.status,r.read()
def main():
    global base
    base=sys.argv[1] if len(sys.argv)>1 else base
    for path in ['/','/health','/docs','/openapi.json','/investigations','/provenance','/logo.svg','/resources']:
        status,body=call(path);assert status==200 and body;print('PASS GET',path)
    for question,route in [('How does cabin airflow influence flame spread in spacecraft?','text'),('Compare burn time PSI-159 at 1.1 bar','structured'),('Compare burn time PSI-159 at 1.1 bar and explain the experiment','hybrid')]:
        status,body=call('/ask',{'question':question});r=json.loads(body);assert r['route']==route;assert r['answer'];print('PASS POST /ask',route)
    status,body=call('/scenario/analyze',{'gravity':'microgravity','sample_type':'Gaseous fuel','oxygen_percent':21,'pressure_psi':14.7,'airflow':.16});assert json.loads(body)['closest_records'];print('PASS POST /scenario/analyze')
    status,body=call('/resources/search',{'question':'Mir fire oxygen generator'});r=json.loads(body);assert r['results'] and not r['judged_eligible'];print('PASS supporting context search')
    try:call('/ask',{'question':'a'});raise AssertionError('short question accepted')
    except urllib.error.HTTPError as e:assert e.code==422;print('PASS request validation')

if __name__=="__main__": main()
