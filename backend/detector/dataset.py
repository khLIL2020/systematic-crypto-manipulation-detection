"""Build immutable feature windows from recorded, timestamp-aligned market data."""
import time
import numpy as np
from .native import features,FEATURES
from .providers import UNIVERSE,sentiment_at
from .model import split_indices

def weak_label(move,excess,threshold):
    return 1 if move>0 and excess>threshold else 2 if move<0 and excess<-threshold else 0

def build_dataset(raw):
    benchmark={r[0]:r for r in raw['candles']['BTC']};articles=raw['articles'];rows=[]
    names={s:n for s,n,_ in UNIVERSE}
    for symbol,candles in raw['candles'].items():
        # Only timestamp intersections; never align unrelated positions.
        aligned=[r for r in candles if r[0] in benchmark]
        for i in range(24,len(aligned)-3):
            window=aligned[i-24:i+1];future=aligned[i+3]
            if future[0]-window[0][0]!=27*300:continue
            p=[r[4] for r in window];b=[benchmark[r[0]][4] for r in window];v=[r[5] for r in window]
            at=window[-1][0]+300;sent,present,count=sentiment_at(articles,symbol,names.get(symbol,symbol),at)
            x=features(p,b,v,sent,present)
            move=np.log(future[4]/p[-1]);market_move=np.log(benchmark[future[0]][4]/b[-1])
            excess=move if symbol=='BTC' else move-market_move
            threshold=max(.0015,1.5*x[3]*np.sqrt(3))
            label=weak_label(move,excess,threshold)
            rows.append({'timestamp':at,'symbol':symbol,'x':x.tolist(),'y':label})
    rows.sort(key=lambda r:(r['timestamp'],r['symbol']))
    if len(rows)<600:raise ValueError('insufficient aligned historical windows')
    ts=[r['timestamp'] for r in rows];a,b,c=split_indices(ts)
    if min(len(a),len(b),len(c))<50:raise ValueError('insufficient purged partitions')
    return {'schema':'features-v1','features':FEATURES,'rows':rows,'train':a.tolist(),'validation':b.tolist(),'test':c.tolist(),'provenance':{'source':'Coinbase Exchange 5m candles + dated Cointelegraph/Google News RSS','raw_hash':raw.get('raw_hash'),'fetched_at':raw['fetched_at'],'label_rule':'15m future log return minus BTC return (BTC uses absolute return), threshold max(0.15%, 1.5*past_vol*sqrt(3)); absolute return must agree with direction','label_kind':'weak anomaly labels; not confirmed manipulation','news':'timestamped preceding 24h headline lexicon; missing=0 with indicator','split':'60/20/20 chronological; 135-minute purge before validation/test','news_coverage':sum(r['x'][1] for r in rows)/len(rows),'counts':{str(k):sum(r['y']==k for r in rows) for k in range(3)}}}
