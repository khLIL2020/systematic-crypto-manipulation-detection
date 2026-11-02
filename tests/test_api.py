import sys,tempfile,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi.testclient import TestClient
from detector.runtime import Runtime
from main import create_app
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.rt=Runtime(self.temp.name);self.client=TestClient(create_app(self.rt,background=False))
    def tearDown(self):self.temp.cleanup()
    def test_missing_data_is_not_a_fabricated_signal(self):
        self.assertEqual(self.client.get('/api/coins').json(),[])
        self.assertEqual(self.client.get('/api/detection/signals').status_code,404)
        self.assertEqual(self.client.post('/api/detection/jobs',json={'kind':'train'}).status_code,409)
        self.assertEqual(self.client.get('/api/dashboard').json()['stats']['coins_scanned'],0)
    def test_job_constraints_and_persistent_queue(self):
        self.assertEqual(self.client.post('/api/detection/jobs',json={'kind':'replay','threads':0}).status_code,422)
        r=self.client.post('/api/detection/jobs',json={'kind':'ingest','days':3})
        self.assertEqual(r.status_code,201)
        self.assertEqual(Runtime(self.temp.name).store.jobs()[0]['id'],r.json()['id'])
    def test_stale_signals_have_null_scores(self):
        self.rt.store.set('snapshot',{'coins':[{'symbol':'BTC','flag':'pump','scanned_at':'old','observed_at':time.time()-1000,'manipulation_score':.9}],'alerts':[]})
        r=self.client.get('/api/detection/signals').json()
        self.assertEqual(r['risk_band'],'unavailable');self.assertIsNone(r['manipulation_score'])
        self.assertEqual(self.client.get('/api/detection/alerts').json()['alerts'],[])
