"""Lifespan-owned scan loop and bounded experiment worker, backed by SQLite."""
import copy,hashlib,json,os,threading,time,platform
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from .store import Store,utc
from .providers import Providers,UNIVERSE,sentiment_at
from .native import features,predict_native,replay,status,FEATURES,BINARY_HASH,PATH
from .model import fit,metrics
from .dataset import build_dataset

ROOT=Path(__file__).resolve().parents[1]

def code_hash():
    h=hashlib.sha256()
    for p in sorted(list((ROOT/'detector').glob('*.py'))+list((ROOT.parent/'native/cpp').glob('*.cpp'))+list((ROOT.parent/'native/cpp').glob('*.h'))):h.update(p.name.encode()+p.read_bytes())
    return h.hexdigest()

LOADED_CODE_HASH=code_hash()

def public_snapshot(snapshot,now=None):
    result=copy.deepcopy(snapshot or {'coins':[],'alerts':[],'last_scan_at':None})
    now=time.time() if now is None else now
    for coin in result.get('coins',[]):
        age=now-coin.get('observed_at',0);coin['age_seconds']=max(0,round(age))
        if age>600 or age< -60:
            coin.update(flag='unavailable',manipulation_score=None,pump_score=None,dump_score=None,data_status='stale',reason='No fresh completed candles')
    result['alerts']=[{**c,'horizon':'next 15 minutes (experimental)'} for c in result.get('coins',[]) if c.get('flag') in ('pump','dump','watch')]
    return result

class Runtime:
    def __init__(self,root=None,providers=None,interval=None):
        self.store=Store(root or os.getenv('SYSTEMATIC_DATA_DIR',ROOT/'data'))
        self.loaded_code_hash=LOADED_CODE_HASH
        self.source_artifact=self.store.artifact({str(p.relative_to(ROOT.parent)):p.read_text() for p in sorted(list((ROOT/'detector').glob('*.py'))+list((ROOT.parent/'native/cpp').glob('*.cpp'))+list((ROOT.parent/'native/cpp').glob('*.h')))})
        self.providers=providers or Providers();self.interval=float(interval or os.getenv('SCAN_INTERVAL_SEC','60'))
        if self.interval<1:raise ValueError('scan interval must be >=1 second')
        self.stop=threading.Event();self.scan_lock=threading.Lock();self.threads=[]
    def start(self):
        self.store.recover()
        for name,target in [('coin-scanner',self.scan_loop),('experiment-worker',self.job_loop)]:
            t=threading.Thread(name=name,target=target,daemon=True);t.start();self.threads.append(t)
    def close(self):
        self.stop.set()
        for t in self.threads:t.join(timeout=20)
    def snapshot(self):
        result=public_snapshot(self.store.get('snapshot'))
        result.update(interval_sec=self.interval,engine=status(),running=any(t.name=='coin-scanner' and t.is_alive() for t in self.threads),apis=self.providers.statuses() or result.get('apis',{}),model=self.store.get('active_model'))
        return result
    def scan_loop(self):
        self.providers.probe_binance()
        while not self.stop.is_set():
            begin=time.monotonic()
            try:self.scan_once()
            except Exception as e:self.store.set('scan_error',str(e))
            self.stop.wait(max(.1,self.interval-(time.monotonic()-begin)))
    def scan_once(self):
        if not self.scan_lock.acquire(blocking=False):return self.snapshot()
        try:
            metadata=self.providers.metadata();articles=self.providers.news();series={};errors={}
            def fetch(entry):
                try:return entry[0],self.providers.candles(entry[0]),None
                except Exception as e:return entry[0],[],str(e)
            with ThreadPoolExecutor(max_workers=3) as pool:
                for symbol,rows,error in pool.map(fetch,UNIVERSE):
                    series[symbol]=rows
                    if error:errors[symbol]=error
            bench={r[0]:r for r in series.get('BTC',[])}
            active=self.store.get('active_model');model=self.store.read_artifact(active['artifact']) if active else None
            coins=[]
            for symbol,name,id in UNIVERSE:
                meta=metadata.get(id,{})
                row={'id':id,'name':name,'symbol':symbol,'image':meta.get('image'),'market_cap':meta.get('market_cap'),'price_change_percentage_24h':meta.get('price_change_percentage_24h'),'current_price':None,'total_volume':meta.get('total_volume'),'flag':'unavailable','manipulation_score':None,'pump_score':None,'dump_score':None,'observed_at':0,'scanned_at':utc(),'data_status':'unavailable','series_source':'coinbase','cadence_seconds':300,'engine':'cpp' if status()['cpp_loaded'] else 'python-fallback','reason':errors.get(symbol,'Waiting for aligned candles or trained model')}
                candles=series[symbol]
                if candles:row.update(current_price=candles[-1][4],observed_at=candles[-1][0]+300)
                aligned=[r for r in candles if r[0] in bench][-25:]
                if len(aligned)==25 and aligned[-1][0]-aligned[0][0]==24*300:
                    p=[r[4] for r in aligned];b=[bench[r[0]][4] for r in aligned];v=[r[5] for r in aligned]
                    at=aligned[-1][0]+300;sent,present,count=sentiment_at(articles,symbol,name,at)
                    x=features(p,b,v,sent,present)
                    row.update(observed_at=at,signals=dict(zip(FEATURES,x.tolist())),sentiment_count=count,news_status='covered' if present else 'missing',volatility=float(x[3]),data_status='live',reason=None)
                    if model:
                        probs=predict_native(model,[x])[0];normal,pump,dump=map(float,probs);risk=1-normal
                        flag='pump' if pump>=.65 and pump>=dump else 'dump' if dump>=.65 else 'watch' if risk>=.5 else 'clear'
                        row.update(flag=flag,manipulation_score=risk,pump_score=pump,dump_score=dump,model_version=active['artifact'][:12],training_job=active['job_id'],experimental=True)
                    else:row.update(reason='No trained model promoted',data_status='untrained')
                coins.append(row)
            snapshot=public_snapshot({'coins':coins,'last_scan_at':utc(),'last_error':'; '.join(f'{k}: {v}' for k,v in errors.items()) or None,'apis':self.providers.statuses()})
            self.store.scan(snapshot);self.store.set('scan_error',None)
            return self.snapshot()
        finally:self.scan_lock.release()
    def enqueue(self,config):
        if code_hash()!=self.loaded_code_hash or (PATH.exists() and hashlib.sha256(PATH.read_bytes()).hexdigest()!=BINARY_HASH):raise ValueError('Source or native library changed: restart backend before submitting jobs')
        config=dict(config)
        if config['kind']!='ingest':
            config['dataset_id']=config.get('dataset_id') or self.store.get('dataset_id')
            if not config['dataset_id']:raise ValueError('No dataset yet; enqueue an ingest job first')
            self.store.read_artifact(config['dataset_id'])
        if config['kind'] in ('replay','score'):
            active=self.store.get('active_model');config['model_id']=config.get('model_id') or (active or {}).get('artifact')
            if not config['model_id']:raise ValueError('No model promoted; train and promote a model first')
            self.store.read_artifact(config['model_id'])
        config['source_artifact']=self.source_artifact;config['code_hash']=self.loaded_code_hash;config['python_version']=platform.python_version();config['numpy_version']=np.__version__
        config['native_binary_hash']=BINARY_HASH if status()['cpp_loaded'] else None
        if sum(j['status'] in ('running','queued') for j in self.store.jobs())>=64:raise ValueError('Job queue full (64); retry when jobs finish')
        return self.store.create_job(config)
    def job_loop(self):
        while not self.stop.is_set():
            queued=[j for j in self.store.jobs()[::-1] if j['status']=='queued']
            if queued:self.run_job(queued[0]['id'])
            else:self.stop.wait(.25)
    def run_job(self,id):
        job=self.store.job(id);self.store.update_job(id,status='running');begin=time.perf_counter()
        try:
            if job.get('code_hash')!=self.loaded_code_hash or code_hash()!=self.loaded_code_hash:raise ValueError('code changed since enqueue; restart and submit a new run')
            if job.get('native_binary_hash')!=BINARY_HASH or (PATH.exists() and hashlib.sha256(PATH.read_bytes()).hexdigest()!=BINARY_HASH):raise ValueError('native library changed; restart backend')
            kind=job['kind'];artifact=None
            if kind=='ingest':
                candles={}
                for symbol,_,_ in UNIVERSE:
                    if self.stop.is_set():raise RuntimeError('ingestion interrupted')
                    candles[symbol]=self.providers.historical(symbol,job.get('days',7))
                raw={'candles':candles,'articles':self.providers.historical_news(job.get('days',7)),'fetched_at':utc()}
                raw_id=self.store.artifact(raw);raw['raw_hash']=raw_id
                data=build_dataset(raw);artifact=self.store.artifact(data);self.store.set('dataset_id',artifact)
                result={'windows':len(data['rows']),'dataset_id':artifact,'raw_id':raw_id,'news_coverage':data['provenance']['news_coverage'],'label_counts':data['provenance']['counts']}
            else:
                data=self.store.read_artifact(job['dataset_id']);x=np.array([r['x'] for r in data['rows']]);y=np.array([r['y'] for r in data['rows']])
                if kind=='train':
                    model=fit(x[data['train']],y[data['train']],seed=job['seed'],l2=job['l2'],epochs=job['epochs'])
                    model.update(dataset_id=job['dataset_id'],code_hash=job['code_hash'],provenance=data['provenance'])
                    artifact=self.store.artifact(model)
                    val=metrics(model,x[data['validation']],y[data['validation']])
                    # Holdout is not exposed for run selection. Only evaluate upon promotion.
                    result={'validation_macro_f1':val['macro_f1'],'validation_accuracy':val['accuracy'],'training_samples':len(data['train']),'validation':val,'model_id':artifact}
                elif kind=='replay':
                    model=self.store.read_artifact(job['model_id']);repeats=job.get('repeats',100)
                    one=replay(model,x,1,repeats);many=replay(model,x,job['threads'],repeats)
                    if abs(one['checksum']-many['checksum'])>1e-7:raise RuntimeError('replay checksum mismatch')
                    result={'baseline_ms':one['elapsed_ms'],'parallel_ms':many['elapsed_ms'],'speedup':one['elapsed_ms']/max(many['elapsed_ms'],1e-9),**{k:v for k,v in many.items() if k!='elapsed_ms'},'workload':'recorded feature-window replay; repeated passes','hardware':platform.machine(),'cpu_count':os.cpu_count()}
                elif kind=='score':
                    model=self.store.read_artifact(job['model_id']);symbol=job.get('symbol','BTC').split('/')[0].upper()
                    selected=[r for r in data['rows'] if r['symbol']==symbol]
                    if not selected:raise ValueError('symbol not present in recorded dataset')
                    predictions=predict_native(model,[r['x'] for r in selected]);artifact=self.store.artifact({'model_id':job['model_id'],'dataset_id':job['dataset_id'],'symbol':symbol,'timestamps':[r['timestamp'] for r in selected],'probabilities':predictions.tolist()})
                    result={'windows_scored':len(selected),'max_score':float((1-predictions[:,0]).max()),'engine':'cpp' if status()['cpp_loaded'] else 'python-fallback'}
                else:raise ValueError('unknown job kind')
            self.store.update_job(id,status='succeeded',metrics=result,artifact_id=artifact,runtime_seconds=time.perf_counter()-begin)
        except Exception as e:self.store.update_job(id,status='failed',error=f'{type(e).__name__}: {e}',runtime_seconds=time.perf_counter()-begin)
    def promote(self,id):
        job=self.store.job(id)
        if job['kind']!='train' or job['status']!='succeeded':raise ValueError('only successful train jobs can be promoted')
        model=self.store.read_artifact(job['artifact_id']);data=self.store.read_artifact(job['dataset_id'])
        selected=[data['rows'][i] for i in data['test']]
        test=metrics(model,[r['x'] for r in selected],[r['y'] for r in selected])
        normal_fraction=sum(r['y']==0 for r in selected)/len(selected)
        test['always_normal_macro_f1']=(2*normal_fraction/(1+normal_fraction))/3
        test['beats_always_normal']=test['macro_f1']>test['always_normal_macro_f1']
        active={'artifact':job['artifact_id'],'job_id':id,'promoted_at':utc(),'heldout':test,'label_kind':model['label_kind'],'experimental':True,'disabled_features':model.get('disabled_features',[]),'quality':'research-only; not validated for trading'}
        self.store.set('active_model',active);return active
