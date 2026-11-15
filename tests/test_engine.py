"""Scientific integrity and routing regressions. Run from project root."""
import sys,json,unittest,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.evidence import ask_flare_up,route_question,chunks,search_text
from app.structured_data import search_structured,load_structured_records,parse_structured_question,_matches
from app.server import scenario,ScenarioRequest
from app.supplemental import search_context, resource_catalog

class EvidenceTests(unittest.TestCase):
    def test_supporting_context_is_separate(self):
        results=search_context('Mir oxygen generator fire')
        self.assertTrue(results)
        self.assertTrue(all(r['judged_eligible'] is False for r in results))
        self.assertEqual(len(resource_catalog()),10)
        active={r['chunk_id'] for r in chunks()}
        self.assertTrue(all(r['chunk_id'] not in active for r in results))
    def test_routing_contract(self):
        decision=route_question('Compare burn time PSI-159 at 1.1 bar and explain')
        self.assertTrue({'route','reason','numeric_term_hits','has_number','has_unit','has_measurement_target','asks_interpretation'} <= decision.keys())
    def test_judged_eligibility(self):
        for r in (*chunks(),*load_structured_records()):
            self.assertIn(r['project_type'],{'Microgravity Investigation','Reduced Gravity Investigation'})
            self.assertNotEqual(r['investigation_id'],'PSI-117')
    def test_no_ground_columns(self):
        for r in load_structured_records(): self.assertNotIn('1-g',r['quantity_name'].lower())
    def test_text(self):
        r=ask_flare_up('How does cabin airflow influence flame spread in spacecraft?')
        self.assertEqual(r['route'],'text');self.assertTrue(r['sources'])
        self.assertTrue(any(s['investigation_id'] in {'PSI-25','PSI-26'} for s in r['sources']))
    def test_structured(self):
        r=ask_flare_up('Compare burn time for normal and inverse flames in PSI-159 at 1.1 bar')
        self.assertEqual(r['route'],'structured');self.assertTrue(r['structured_results'])
        for x in r['structured_results']: self.assertLessEqual(abs(x['pressure_bar']-1.1),.015)
        both=search_structured('Compare burn time for normal and inverse flames in PSI-159')['results']
        self.assertEqual({x['conditions'].get('Flame Type') for x in both},{'Normal','Inverse'})
    def test_hybrid(self):
        r=ask_flare_up('Compare burn time in PSI-159 at 1.1 bar and explain the experiment')
        self.assertEqual(r['route'],'hybrid');self.assertTrue(r['sources']);self.assertTrue(r['structured_results'])
    def test_flex(self):
        r=search_structured('Visible flame extinction diameter in PSI-69')
        self.assertTrue(r['results']);self.assertTrue(all(x['unit']=='mm' for x in r['results']))
    def test_unknown_units(self):
        r=search_structured('Compare Zst PSI-159')
        self.assertTrue(r['results']);self.assertTrue(all(x['unit'] is None for x in r['results']))
    def test_no_fabricated_result(self):
        self.assertEqual(search_structured('Compare burn time PSI-159 at 99 bar')['results'],[])
        self.assertEqual(search_structured('What is the maximum safe astronaut exposure?')['results'],[])
    def test_unknown_text(self): self.assertEqual(search_text('quasar cryptocurrency football'),[])
    def test_legacy_excluded_but_parser_preserved(self):
        q='Compare model and experiment Dext_cool at 0.5 atm'
        self.assertEqual(ask_flare_up(q)['structured_results'],[])
        records=[json.loads(l) for l in next((ROOT/'legacy').glob('*Dext*')).read_text().splitlines()]
        matches=[r for r in records if _matches(r,parse_structured_question(q))]
        self.assertEqual({r['series_type'] for r in matches},{'model','experiment'})
    def test_arabic_topic(self): self.assertTrue(search_text('كيف يؤثر تدفق الهواء على انتشار اللهب في الجاذبية الصغرى'))
    def test_scenario_no_false_match(self):
        r=scenario(ScenarioRequest(gravity='earth',sample_type='Fabric'))
        self.assertEqual(r['closest_records'],[]);self.assertFalse(r['evidence_match']['exact_match'])
    def test_scenario_pressure_only(self):
        r=scenario(ScenarioRequest());self.assertTrue(r['closest_records'])
        self.assertFalse(r['evidence_match']['exact_match'])
        self.assertIn('Pressure only',r['closest_records'][0]['match_basis'])
if __name__=='__main__':unittest.main(verbosity=2)
