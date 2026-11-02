"""Reproducible softmax regression; labels describe future price anomalies, not proven fraud."""
import hashlib,json
import numpy as np
from .native import FEATURES
VERSION='softmax-v2'
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def split_indices(ts):
    ts=np.asarray(ts); unique=np.unique(ts)
    if len(unique)<200:raise ValueError('need at least 200 distinct timestamps')
    a,b=unique[int(len(unique)*.6)],unique[int(len(unique)*.8)]
    # 24-bar feature lookback + 3-bar future label; strict separation.
    purge=27*300
    return np.where(ts<a-purge)[0],np.where((ts>=a)&(ts<b-purge))[0],np.where(ts>=b)[0]
def fit(x,y,seed=42,l2=.01,epochs=350):
    x=np.asarray(x,float); y=np.asarray(y,int)
    if x.ndim!=2 or x.shape[1]!=8 or len(x)!=len(y) or not np.isfinite(x).all():raise ValueError('invalid training matrix')
    if set(y)!={0,1,2}:raise ValueError('training requires all three classes')
    mean=x.mean(axis=0); std=x.std(axis=0); disabled=std<1e-8; scale=np.maximum(std,1e-8)
    z=np.column_stack((np.clip((x-mean)/scale,-12,12),np.ones(len(x))))
    w=np.random.default_rng(seed).normal(0,.005,(9,3))
    w[:8][disabled]=0
    targets=np.eye(3)[y]
    # Inverse-frequency weights make minority anomaly examples visible; scores uncalibrated.
    weights=len(y)/(3*np.bincount(y,minlength=3))[y]
    for _ in range(epochs):
        logits=z@w; logits-=logits.max(axis=1,keepdims=True)
        p=np.exp(logits);p/=p.sum(axis=1,keepdims=True)
        grad=z.T@((p-targets)*weights[:,None])/len(x)
        grad[:-1]+=l2*w[:-1];w-=.08*grad
    return {'version':VERSION,'features':FEATURES,'classes':['normal','pump','dump'],'mean':mean.tolist(),'scale':scale.tolist(),'weights':w.tolist(),'seed':seed,'l2':l2,'epochs':epochs,'label_kind':'weak future-price anomaly','calibrated':False,'horizon_minutes':15,'disabled_features':[FEATURES[i] for i in range(8) if disabled[i]]}
def predict(model,x):
    x=np.asarray(x,float);z=np.column_stack((np.clip((x-model['mean'])/model['scale'],-12,12),np.ones(len(x))))
    logits=z@np.asarray(model['weights']);logits-=logits.max(axis=1,keepdims=True)
    p=np.exp(logits);return p/p.sum(axis=1,keepdims=True)
def metrics(model,x,y):
    pred=predict(model,x).argmax(axis=1);y=np.asarray(y)
    cm=np.zeros((3,3),int)
    for a,b in zip(y,pred):cm[a,b]+=1
    precision=np.diag(cm)/np.maximum(cm.sum(axis=0),1);recall=np.diag(cm)/np.maximum(cm.sum(axis=1),1)
    f1=2*precision*recall/np.maximum(precision+recall,1e-12)
    return {'macro_f1':float(f1.mean()),'accuracy':float(np.mean(pred==y)),'precision':precision.tolist(),'recall':recall.tolist(),'confusion_matrix':cm.tolist(),'samples':len(y)}
