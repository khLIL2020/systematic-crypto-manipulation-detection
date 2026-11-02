import sys,unittest,tempfile,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from detector.providers import sentiment_at,validate_candles,UNIVERSE
from detector.runtime import Runtime
from detector.model import fit
class Feed:
    def __init__(self):self.fail=False
    def metadata(self):return {}
    def news(self):return []
    def statuses(self):return {'coinbase':{'status':'failed' if self.fail else 'working'}}
    def candles(self,symbol):
        if self.fail:raise RuntimeError('offline')
        end=int(time.time()//300)*300
        return [[end-(30-i)*300,100,101,100,100+i*.01,5+i] for i in range(30)]
class ObservationTests(unittest.TestCase):
    def test_news_cannot_leak_from_the_future(self):
        articles=[{'title':'Bitcoin gains','timestamp':101,'sentiment':1}]
        self.assertEqual(sentiment_at(articles,'BTC','Bitcoin',100),(0.,0,0))
        self.assertEqual(sentiment_at(articles,'BTC','Bitcoin',102),(1.,1,1))
    def test_incomplete_and_nonfinite_candles_are_rejected(self):
        r=[[0,1,2,1,1,1],[300,1,2,1,1,1],[0,1,2,1,float('nan'),1]]
        self.assertEqual(len(validate_candles(r,350)),1)
    def test_provider_outage_clears_previous_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            feed=Feed();rt=Runtime(d,feed)
            x=np.random.default_rng(1).normal(size=(60,8));y=np.arange(60)%3;m=fit(x,y)
            h=rt.store.artifact(m);rt.store.set('active_model',{'artifact':h,'job_id':'test'})
            a=rt.scan_once();self.assertEqual(sum(c['manipulation_score'] is not None for c in a['coins']),len(UNIVERSE))
            feed.fail=True;b=rt.scan_once()
            self.assertEqual(b['alerts'],[])
            self.assertTrue(all(c['flag']=='unavailable' for c in b['coins']))
    def test_replay_visits_real_feature_rows(self):
        from detector.native import replay,predict_native
        rng=np.random.default_rng(1);x=rng.normal(size=(100,8));y=np.arange(100)%3;m=fit(x,y)
        expected=float((predict_native(m,x)@np.array([0.,1.,2.])).sum())*13
        self.assertAlmostEqual(replay(m,x,4,13)['checksum'],expected,places=8)
