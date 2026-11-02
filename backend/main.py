"""Local Systematic API. No remote database mutation or demo metrics."""
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from typing import Literal
from detector.runtime import Runtime
from detector.native import FEATURES

class JobCreate(BaseModel):
    kind:Literal['ingest','train','replay','score']
    symbol:str=Field(default='BTC/USDT',max_length=30)
    seed:int=Field(default=42,ge=0,le=2**32-1)
    threads:int=Field(default=4,ge=1,le=64)
    notes:str=Field(default='',max_length=500)
    l2:float=Field(default=.01,ge=0,le=10)
    epochs:int=Field(default=350,ge=20,le=2000)
    days:int=Field(default=7,ge=3,le=30)
    repeats:int=Field(default=100,ge=1,le=10000)
    dataset_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    model_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')

def create_app(runtime=None,background=True):
    rt=runtime or Runtime()
    @asynccontextmanager
    async def lifespan(app):
        if background:rt.start()
        yield
        if background:rt.close()
    app=FastAPI(title='Systematic',version='1.0.0',description='Experimental ML crypto anomaly risk; automatic scans, durable experiments and measured C++ replay.',lifespan=lifespan)
    app.state.runtime=rt
    app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000','http://127.0.0.1:3000'],allow_methods=['GET','POST'],allow_headers=['Content-Type'])
    @app.get('/')
    def root():return {'service':'Systematic','ui':'http://127.0.0.1:3000','docs':'http://127.0.0.1:8000/docs','version':'1.0.0'}
    @app.get('/api/coins')
    def coins():return rt.snapshot()['coins']
    @app.get('/api/detection/scan')
    def scan():return rt.snapshot()
    @app.get('/api/detection/alerts')
    def alerts():
        s=rt.snapshot();return {'as_of':s.get('last_scan_at'),'alerts':s['alerts'],'last_error':s.get('last_error'),'engine':s['engine']}
    @app.get('/api/detection/health')
    def health():
        s=rt.snapshot();return {'apis':s['apis'],'engine':s['engine'],'running':s['running'],'last_scan_at':s.get('last_scan_at'),'last_error':rt.store.get('scan_error') or s.get('last_error'),'interval_sec':s['interval_sec'],'active_model':s['model'],'dataset_id':rt.store.get('dataset_id'),'limitations':['Weak price-anomaly labels are not verified manipulation.','Scores are experimental and uncalibrated.','News sentiment uses a headline lexicon; no social feed.'],'disabled':{'timescaledb':'Removed legacy random-data writer; SQLite owns real scan metrics','clerk':'Local app does not require auth keys'}}
    @app.get('/api/detection/signals')
    def signals(symbol:str='BTC/USDT'):
        want=symbol.split('/')[0].upper();s=rt.snapshot()
        coin=next((c for c in s['coins'] if c['symbol']==want),None)
        if coin is None:raise HTTPException(404,'Symbol not scanned yet or outside configured universe')
        return {**coin,'as_of':coin['scanned_at'],'risk_band':coin['flag'],'signals':coin.get('signals',{}),'model':{'name':coin.get('model_version','untrained'),'features':FEATURES}}
    @app.get('/api/detection/jobs')
    def jobs():return rt.store.jobs()
    @app.get('/api/detection/jobs/{id}')
    def job(id:str):
        try:return rt.store.job(id)
        except KeyError:raise HTTPException(404,'Job not found')
    @app.post('/api/detection/jobs',status_code=201)
    def enqueue(body:JobCreate):
        try:return rt.enqueue(body.model_dump())
        except (ValueError,FileNotFoundError) as e:raise HTTPException(409,str(e))
    @app.post('/api/detection/jobs/{id}/rerun',status_code=201)
    def rerun(id:str):
        try:
            old=rt.store.job(id)
            if old.get('code_hash')!=rt.loaded_code_hash:raise ValueError('Run uses a different code version; inspect its source artifact and create a new comparison job')
            config={k:old[k] for k in JobCreate.model_fields if k in old}
            return rt.enqueue(JobCreate(**config).model_dump())
        except KeyError:raise HTTPException(404,'Job not found')
        except (ValueError,FileNotFoundError) as e:raise HTTPException(409,str(e))
    @app.post('/api/detection/models/promote/{id}')
    def promote(id:str):
        try:return rt.promote(id)
        except KeyError:raise HTTPException(404,'Job not found')
        except ValueError as e:raise HTTPException(409,str(e))
    @app.get('/api/detection/artifacts/{hash}')
    def artifact(hash:str):
        try:return rt.store.read_artifact(hash)
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Artifact not found or invalid')
    @app.get('/api/dashboard')
    def dashboard():
        s=rt.snapshot();coins=s['coins'];scored=[c for c in coins if c.get('manipulation_score') is not None]
        return {'stats':{'coins_scanned':len(scored),'flagged_windows':len(s['alerts']),'experiment_runs':sum(j['status']=='succeeded' for j in rt.store.jobs()),'avg_risk':sum(c['manipulation_score'] for c in scored)/max(1,len(scored))},'as_of':s.get('last_scan_at'),'chains':[]}
    @app.get('/api/detection/history')
    def history():
        return [{'time':s['last_scan_at'],'risk':sum(c.get('manipulation_score') or 0 for c in s['coins'])/max(1,sum(c.get('manipulation_score') is not None for c in s['coins'])),'coverage':sum(c.get('manipulation_score') is not None for c in s['coins']),'alerts':len(s['alerts'])} for s in rt.store.history()]
    return app

app=create_app()
