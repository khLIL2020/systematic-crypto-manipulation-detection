import sys, unittest, tempfile, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

class DetectorTests(unittest.TestCase):
    def test_native_features_match_python_and_reject_bad_prices(self):
        from detector.native import features, python_features
        p=np.exp(np.linspace(0, .2, 25)); b=np.exp(np.linspace(0, .1, 25)); v=np.arange(25)+1.
        np.testing.assert_allclose(features(p,b,v,.4,1),python_features(p,b,v,.4,1),atol=1e-10)
        with self.assertRaises(ValueError): features([0]*25,b,v,0,0)
        self.assertTrue(np.isfinite(features(np.ones(25),np.ones(25),v,0,0)).all())
    def test_training_is_reproducible_and_native_predictions_match(self):
        from detector.model import fit, predict
        from detector.native import predict_native, replay
        rng=np.random.default_rng(12); x=rng.normal(size=(400,8)); y=np.where(x[:,4]>.5,1,np.where(x[:,4]<-.5,2,0))
        a=fit(x,y,seed=5,l2=.01); b=fit(x,y,seed=5,l2=.01)
        self.assertEqual(a,b)
        np.testing.assert_allclose(predict(a,x),predict_native(a,x),atol=1e-10)
        one=replay(a,x,1,3); four=replay(a,x,4,3)
        self.assertEqual(one['windows_scored'],1200)
        self.assertAlmostEqual(one['checksum'],four['checksum'],places=8)
    def test_chronological_split_purges_overlap(self):
        from detector.model import split_indices
        ts=np.arange(1000)*300
        a,b,c=split_indices(ts)
        self.assertLess(ts[a[-1]]+27*300,ts[b[0]])
        self.assertLess(ts[b[-1]]+27*300,ts[c[0]])
    def test_store_persists_and_recovers_jobs(self):
        from detector.store import Store
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)); j=s.create_job({'kind':'train','seed':1})
            s.update_job(j['id'],status='running')
            t=Store(Path(d)); t.recover()
            self.assertEqual(t.jobs()[0]['status'],'failed')
            self.assertIn('interrupted', t.jobs()[0]['error'])
    def test_stale_snapshot_does_not_return_clear_or_alert(self):
        from detector.runtime import public_snapshot
        old={'coins':[{'flag':'pump','observed_at':time.time()-1000,'manipulation_score':.9}], 'alerts':[{'flag':'pump'}]}
        result=public_snapshot(old,now=time.time())
        self.assertEqual(result['coins'][0]['flag'],'unavailable')
        self.assertIsNone(result['coins'][0]['manipulation_score'])
        self.assertEqual(result['alerts'],[])

if __name__=='__main__':unittest.main()
