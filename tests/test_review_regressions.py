import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
class ReviewTests(unittest.TestCase):
    def test_directional_label_agrees_with_absolute_move(self):
        from detector.dataset import weak_label
        self.assertEqual(weak_label(-.001,.01,.001),0)
        self.assertEqual(weak_label(.001,-.01,.001),0)
        self.assertEqual(weak_label(.02,.02,.001),1)
        self.assertEqual(weak_label(-.02,-.02,.001),2)
    def test_constant_feature_cannot_affect_prediction(self):
        from detector.model import fit,predict
        x=np.random.default_rng(1).normal(size=(300,8));x[:,0]=0;y=np.arange(300)%3
        m=fit(x,y,l2=.001);a=x[:1].copy();b=a.copy();b[0,0]=1
        np.testing.assert_array_equal(predict(m,a),predict(m,b))
        self.assertIn('sentiment',m['disabled_features'])
    def test_source_change_rejects_misattributed_job(self):
        from detector.runtime import Runtime
        with tempfile.TemporaryDirectory() as d:
            rt=Runtime(d)
            with patch('detector.runtime.code_hash',return_value='changed'):
                with self.assertRaisesRegex(ValueError,'restart'):rt.enqueue({'kind':'ingest'})
    def test_invalid_json_marks_provider_failed(self):
        from detector.providers import Providers
        class Response:
            status_code=200
            def raise_for_status(self):pass
            def json(self):raise ValueError('bad json')
        p=Providers()
        with patch('detector.providers.requests.get',return_value=Response()):
            self.assertEqual(p.metadata(),{})
            with self.assertRaises(ValueError):p.candles('BTC')
        self.assertEqual(p.statuses()['coingecko']['status'],'failed')
        self.assertEqual(p.statuses()['coinbase:BTC']['status'],'failed')
