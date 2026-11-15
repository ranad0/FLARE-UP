import json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.evidence import ask_flare_up,chunks
from app.structured_data import load_structured_records,search_structured
from app.synthesis import synthesize,_validate,_resolve_quotes,_CACHE

class HandoffTests(unittest.TestCase):
    def test_new_saffire_fields_exact(self):
        for question,values,unit in [('burn time',{420,70},'s'),('ignition time',{8},'s'),('ignition power',{182},'W')]:
            with patch.dict(os.environ,{'GROQ_API_KEY':''}):r=ask_flare_up(question+' PSI-98')
            self.assertEqual(r['route'],'structured')
            self.assertEqual({x['value'] for x in r['structured_results']},values)
            self.assertEqual({x['unit'] for x in r['structured_results']},{unit})
            self.assertEqual(len(r['structured_results']),2)
    def test_new_design_document_is_objective(self):
        selected=[r for r in chunks() if 'Baseline Concept' in r['source_file']]
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]['evidence_role'],'research_objective')
        self.assertIn('not a reflight result',selected[0]['scope_review'])
    def test_numeric_dedup_and_originals(self):
        records=load_structured_records()
        keys=[(r['source_sha256'],r['source_row_number'],r['source_column_name']) for r in records]
        self.assertEqual(len(keys),len(set(keys)))
        migrated=[r for r in records if 'migration' in r]
        self.assertEqual(len(migrated),6)
        for r in migrated:
            for f in ('value','value_raw','unit','conditions','source_row_values','quality_flags','series_type'):
                self.assertEqual(r[f],r['migration']['original_record'][f])
            self.assertEqual(r['schema_version'],'3.0')
    def test_pending_and_context_never_judged(self):
        for r in (*chunks(),*load_structured_records()):
            self.assertNotEqual(r['investigation_id'],'PSI-117')
            self.assertNotIn('nasa-safety-cases',r['source_relative_path'])
            self.assertNotEqual(r.get('content_type'),'dataset_index')
            self.assertNotEqual(r.get('judged_eligible'),False)
    def test_audit_manifests_passed(self):
        audit=json.loads((ROOT/'data_handoffs/handoff_3/audit_report.json').read_text(encoding='utf8'))
        self.assertTrue(all(not m['failed'] for m in audit['manifest_checks']))
        self.assertEqual(sum(x['duplicate_same_value_unit'] for x in audit['numeric_comparison']),5607)

class SynthesisTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()
        self.sources=[{'text':'Airflow influences flame spread under the tested conditions. These findings do not establish safe operating limits.','evidence_role':'flight_results','citation_url':'https://psi.nasa.gov/physci/repo/data/investigations/PSI-25','source_file':'report.pdf','source_location':'page:27'}]
        self.valid={'reported_by_sources':[{'text':'Airflow influences flame spread under the tested conditions.','supports':[{'source_id':'T1','quote':self.sources[0]['text']}]}],'interpretation':[]}
    def test_missing_key_never_calls_provider(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':''}),patch('app.synthesis._call') as call:
            r=synthesize('How does airflow influence flame spread?','text',self.sources,[])
            call.assert_not_called();self.assertEqual(r['status'],'extractive-no-key');self.assertTrue(r['reported_by_sources'])
            self.assertIn('do not establish',r['reported_by_sources'][0]['text'])
    def test_grounded_synthesis(self):
        draft=json.loads(json.dumps(self.valid));draft['reported_by_sources'][0]['supports']=[{'source_id':'T1','quote_id':'T1.S1'}]
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=[draft,{'supported':True}]):
            r=synthesize('airflow','text',self.sources,[])
            self.assertEqual(r['status'],'groq-grounded');self.assertEqual(r['reported_by_sources'][0]['source_ids'],['T1'])
    def test_rejected_entailment_falls_back(self):
        draft=json.loads(json.dumps(self.valid));draft['reported_by_sources'][0]['supports']=[{'source_id':'T1','quote_id':'T1.S1'}]
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=[draft,{'supported':False}]):
            self.assertEqual(synthesize('airflow','text',self.sources,[])['status'],'extractive-fallback')
    def test_verified_cache_is_bound_to_evidence(self):
        draft=json.loads(json.dumps(self.valid));draft['reported_by_sources'][0]['supports']=[{'source_id':'T1','quote_id':'T1.S1'}]
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=[draft,{'supported':True},TimeoutError]) as call:
            first=synthesize('airflow','text',self.sources,[])
            self.assertEqual(first,synthesize('airflow','text',self.sources,[]))
            self.assertEqual(call.call_count,2)
            changed=[{**self.sources[0],'text':self.sources[0]['text']+' Additional context.'}]
            self.assertEqual(synthesize('airflow','text',changed,[])['status'],'extractive-fallback')
            self.assertEqual(call.call_count,3)
    def test_invalid_claims_fall_back(self):
        for bad in ('Flames burn for 20 seconds.','Flames burn for twenty seconds.','Airflow doubles the spread rate.'):
            claim=json.loads(json.dumps(self.valid));claim['reported_by_sources'][0]['text']=bad
            claim['reported_by_sources'][0]['supports']=[{'source_id':'T1','quote_id':'T1.S1'}]
            with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=[claim,{'supported':False}]):
                self.assertEqual(synthesize('airflow','text',self.sources,[])['status'],'extractive-fallback')
    def test_fabricated_quote_and_id_rejected(self):
        for field,value in [('source_id','T99'),('quote','Invented scientific finding not in the source passage.')]:
            claim=json.loads(json.dumps(self.valid));claim['reported_by_sources'][0]['supports'][0][field]=value
            with self.assertRaises(ValueError):_validate(claim,{'T1':self.sources[0]})
    def test_network_failure_falls_back(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=TimeoutError):
            self.assertEqual(synthesize('airflow','text',self.sources,[])['status'],'extractive-fallback')
    def test_quote_ids_resolve_to_source_text(self):
        d={'reported_by_sources':[{'text':'A supported claim.','supports':[{'source_id':'T1','quote_id':'T1.S1'}]}],'interpretation':[]}
        r=_resolve_quotes(d,{'T1':{'quotations':{'T1.S1':self.sources[0]['text']}}})
        self.assertEqual(r['reported_by_sources'][0]['supports'][0]['quote'],self.sources[0]['text'])
        with self.assertRaises(ValueError):_resolve_quotes(d,{'T1':{'quotations':{}}})
    def test_bounded_repair_keeps_checks(self):
        draft=json.loads(json.dumps(self.valid));draft['reported_by_sources'][0]['supports']=[{'source_id':'T1','quote_id':'T1.S1'}]
        bad=json.loads(json.dumps(draft));bad['reported_by_sources'][0]['text']='The flame burns for twenty seconds.'
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-not-a-real-key'}),patch('app.synthesis._call',side_effect=[bad,draft,{'supported':True}]) as call:
            self.assertEqual(synthesize('airflow','text',self.sources,[])['status'],'groq-grounded')
            self.assertEqual(call.call_count,3)
    def test_unknown_unit_stays_unknown_in_summary(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':''}):r=ask_flare_up('Compare Zst PSI-159')
        self.assertTrue(r['structured_results']);self.assertTrue(all(x['unit'] is None for x in r['structured_results']))
        self.assertIn('unit unknown',r['synthesis']['reported_by_sources'][0]['text'])
if __name__=='__main__':unittest.main()
