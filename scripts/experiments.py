"""Collect data and run a reproducible 32-run sweep entirely through REST."""
import json,time,urllib.request,urllib.error,argparse
from pathlib import Path
API='http://127.0.0.1:8000/api/detection'
def call(path,data=None):
    req=urllib.request.Request(API+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def wait(id):
    while True:
        j=call('/jobs/'+id)
        if j['status']=='failed':raise RuntimeError(j['error'])
        if j['status']=='succeeded':return j
        time.sleep(2)
def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh-data',action='store_true');p.add_argument('--days',type=int,default=7);args=p.parse_args()
    health=call('/health')
    if args.refresh_data or not health['dataset_id']:
        j=call('/jobs',{'kind':'ingest','days':args.days,'notes':'Public historical candles and timestamped news; no synthetic data'})
        print('Ingest queued',j['id'],flush=True);ingest=wait(j['id']);print('Dataset',ingest['metrics'],flush=True)
    runs=[]
    for l2 in [.001,.01,.1,1.]:
        for seed in range(8):
            runs.append(call('/jobs',{'kind':'train','seed':seed,'l2':l2,'epochs':350,'notes':'32-run baseline sweep; select by validation macro F1 only'}))
    completed=[]
    for j in runs:
        done=wait(j['id']);completed.append(done);print('Trained',done['id'],done['metrics']['validation_macro_f1'],flush=True)
    best=max(completed,key=lambda j:j['metrics']['validation_macro_f1'])
    promoted=call('/models/promote/'+best['id'],{})
    print('Promoted',json.dumps(promoted),flush=True)
    replay=wait(call('/jobs',{'kind':'replay','threads':4,'repeats':1000,'notes':'Measured single vs four-worker native recorded-window replay'})['id'])
    duplicate=wait(call('/jobs/'+best['id']+'/rerun',{})['id'])
    result={'runs':[j['id'] for j in completed],'best_job':best['id'],'active_model':promoted,'replay':replay,'reproducibility':{'rerun_id':duplicate['id'],'same_model_hash':duplicate['artifact_id']==best['artifact_id'],'same_config_hash':duplicate['config_hash']==best['config_hash']}}
    path=Path(__file__).resolve().parents[1]/'experiment-results.json';path.write_text(json.dumps(result,indent=2));print('Saved',path,flush=True)
if __name__=='__main__':main()
