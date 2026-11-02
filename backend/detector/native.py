"""One feature/model contract shared by native and Python adapters."""
import ctypes as C
import hashlib
import platform
from pathlib import Path
import numpy as np
FEATURES=['sentiment','news_present','price_correlation','volatility','momentum','excess_momentum','volume_z','volatility_ratio']
PATH=Path(__file__).resolve().parents[1]/'native_lib'/('libscore_engine.dylib' if platform.system()=='Darwin' else 'libscore_engine.so')
BINARY_HASH=hashlib.sha256(PATH.read_bytes()).hexdigest() if PATH.exists() else None
LIB=None
ERROR=None
try:
    LIB=C.CDLL(str(PATH)); P=C.POINTER(C.c_double)
    LIB.extract_features.argtypes=[P,P,P,C.c_int,C.c_double,C.c_double,P]; LIB.extract_features.restype=C.c_int
    LIB.score_batch.argtypes=[P,C.c_int,P,P,P,P]; LIB.score_batch.restype=C.c_int
    LIB.replay_windows.argtypes=[P,C.c_int,P,P,P,C.c_int,C.c_int,P]; LIB.replay_windows.restype=C.c_double
except (OSError,AttributeError) as e: LIB=None; ERROR=str(e)
def array(x): return np.ascontiguousarray(x,dtype=np.float64)
def ptr(x):return x.ctypes.data_as(C.POINTER(C.c_double))
def status():return {'cpp_loaded':LIB is not None,'detail':ERROR or str(PATH),'lock_free':bool(LIB and LIB.work_index_lock_free())}
def validate(p,b,v):
    p,b,v=map(array,(p,b,v))
    if p.ndim!=1 or b.shape!=p.shape or v.shape!=p.shape or len(p)<25:raise ValueError('need >=25 aligned candles')
    if not all(np.isfinite(x).all() for x in (p,b,v)) or np.any(p<=0) or np.any(b<=0) or np.any(v<0):raise ValueError('invalid price/volume')
    return p,b,v
def python_features(p,b,v,sent,present):
    p,b,v=validate(p,b,v); r=np.diff(np.log(p)); br=np.diff(np.log(b)); vol=np.std(r,ddof=1)
    var=np.sum((r-r.mean())**2); bv=np.sum((br-br.mean())**2)
    corr=np.sum((r-r.mean())*(br-br.mean()))/np.sqrt(var*bv) if var*bv>1e-24 else 0.
    return array([sent,present,corr,vol,r[-3:].sum(),r[-3:].sum()-br[-3:].sum(),np.clip((v[-1]-v[:-1].mean())/max(np.std(v[:-1],ddof=1),1e-9),-10,10),min(10,np.sqrt(np.mean(r[-3:]**2))/max(vol,1e-9))])
def features(p,b,v,sent=0.,present=0.):
    p,b,v=validate(p,b,v)
    if not np.isfinite([sent,present]).all():raise ValueError('invalid sentiment')
    if LIB is None:return python_features(p,b,v,sent,present)
    out=np.zeros(8)
    if LIB.extract_features(ptr(p),ptr(b),ptr(v),len(p),sent,present,ptr(out))!=0:raise ValueError('native feature rejection')
    return out
def params(model):return tuple(array(model[k]) for k in ('mean','scale','weights'))
def predict_native(model,x):
    from .model import predict
    x=array(x).reshape(-1,8)
    if not np.isfinite(x).all():raise ValueError('nonfinite features')
    if LIB is None:return predict(model,x)
    mean,scale,w=params(model); out=np.zeros((len(x),3))
    LIB.score_batch(ptr(x),len(x),ptr(mean),ptr(scale),ptr(w),ptr(out));return out
def replay(model,x,threads=4,repeats=100):
    if LIB is None:raise RuntimeError('C++ required for replay; run make -C native/cpp')
    if not 1<=threads<=64 or not 1<=repeats<=10000:raise ValueError('invalid replay size')
    x=array(x).reshape(-1,8)
    if not len(x) or not np.isfinite(x).all():raise ValueError('invalid replay data')
    mean,scale,w=params(model); checksum=C.c_double()
    ms=LIB.replay_windows(ptr(x),len(x),ptr(mean),ptr(scale),ptr(w),threads,repeats,C.byref(checksum))
    return {'elapsed_ms':ms,'checksum':checksum.value,'windows_scored':len(x)*repeats,'unique_windows':len(x),'repeats':repeats,'threads':threads,'engine':'cpp','lock_free':bool(LIB.work_index_lock_free())}
