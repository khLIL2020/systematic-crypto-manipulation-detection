"""Public-feed adapters preserve timestamps, failures and missingness."""
import math,re,time,threading,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import requests

UNIVERSE=[('BTC','Bitcoin','bitcoin'),('ETH','Ethereum','ethereum'),('SOL','Solana','solana'),('DOGE','Dogecoin','dogecoin'),('XRP','XRP','ripple'),('ADA','Cardano','cardano'),('LINK','Chainlink','chainlink'),('AVAX','Avalanche','avalanche-2')]
POS={'surge','surges','rally','rallies','gain','gains','bullish','approval','approved','record','soars','rise','rises','breakout','buy','adoption'}
NEG={'crash','crashes','dump','drops','drop','loss','losses','bearish','hack','hacked','fraud','scam','plunge','falls','fall','sell','liquidation','liquidations'}

def text_score(text):
    words=re.findall(r'[a-z]+',text.lower());pos=sum(w in POS for w in words);neg=sum(w in NEG for w in words)
    return (pos-neg)/max(1,pos+neg)
def sentiment_at(articles,symbol,name,at):
    matched=[]
    pattern=re.compile(r'\b(?:'+re.escape(symbol)+'|'+re.escape(name)+r')\b',re.I)
    for a in articles:
        if at-86400<=a['timestamp']<=at and pattern.search(a['title']):matched.append(a)
    return (sum(a['sentiment'] for a in matched)/len(matched) if matched else 0.),int(bool(matched)),len(matched)
def validate_candles(rows,now):
    candles={}
    for r in rows:
        if not isinstance(r,list) or len(r)<6:continue
        try:
            t,low,high,op,close,vol=map(float,r[:6])
            if all(math.isfinite(x) for x in (t,low,high,op,close,vol)) and t%300==0 and t+300<=now and min(low,high,op,close)>0 and vol>=0:
                candles[int(t)]=[int(t),low,high,op,close,vol]
        except (ValueError,TypeError):continue
    return [candles[t] for t in sorted(candles)]
class Providers:
    def __init__(self):
        self.health={};self.lock=threading.Lock();self.cache={}
    def mark(self,key,ok,detail,status=None):
        with self.lock:self.health[key]={'status':'working' if ok else 'failed','detail':detail,'http_status':status,'checked_at':datetime.now(timezone.utc).isoformat()}
    def statuses(self):
        with self.lock:return {k:dict(v) for k,v in self.health.items()}
    def request(self,key,url,params=None):
        try:
            r=requests.get(url,params=params,headers={'User-Agent':'SystematicResearch/1.0'},timeout=(5,12))
            if r.status_code==429:
                self.mark(key,False,'Rate limited; no fabricated fallback',429);r.raise_for_status()
            r.raise_for_status();self.mark(key,True,'HTTP request succeeded',r.status_code);return r
        except requests.RequestException as e:
            code=e.response.status_code if getattr(e,'response',None) is not None else None
            self.mark(key,False,f'{type(e).__name__}: {str(e)[:180]}',code);raise
    def candles(self,symbol,start=None,end=None):
        params={'granularity':300}
        if start is not None:params['start']=datetime.fromtimestamp(start,timezone.utc).isoformat()
        if end is not None:params['end']=datetime.fromtimestamp(end,timezone.utc).isoformat()
        key=f'coinbase:{symbol}'
        try:rows=self.request(key,f'https://api.exchange.coinbase.com/products/{symbol}-USD/candles',params).json()
        except ValueError as e:self.mark(key,False,'Invalid JSON candle payload');raise ValueError('Invalid JSON candle payload') from e
        if not isinstance(rows,list):self.mark(key,False,'invalid candle payload');raise ValueError('invalid candles')
        valid=validate_candles(rows,time.time())
        if len(valid)<25:self.mark(key,False,'insufficient completed candles');raise ValueError('insufficient candles')
        self.mark(key,True,f'{len(valid)} completed 5m candles; USD product',200)
        return valid
    def historical(self,symbol,days=7):
        end=int(time.time()//300)*300;start=end-days*86400;data={}
        for begin in range(start,end,299*300):
            rows=self.candles(symbol,begin,min(begin+299*300,end))
            for r in rows:
                if start<=r[0]<end:data[r[0]]=r
            time.sleep(.12)
        return [data[t] for t in sorted(data)]
    def metadata(self):
        cached=self.cache.get('metadata')
        if cached and time.monotonic()-cached[0]<300:return cached[1]
        try:
            rows=self.request('coingecko','https://api.coingecko.com/api/v3/coins/markets',{'vs_currency':'usd','ids':','.join(x[2] for x in UNIVERSE),'sparkline':'false'}).json()
            if not isinstance(rows,list):raise ValueError('invalid metadata')
            result={r['id']:r for r in rows};self.cache['metadata']=(time.monotonic(),result);return result
        except Exception as e:
            if self.health.get('coingecko',{}).get('status')!='failed':self.mark('coingecko',False,f'Invalid metadata payload: {e}')
            # Metadata is optional; candle prices continue without a market cap.
            return {}
    def parse_news(self,key,response):
        try:
            root=ET.fromstring(response.content);articles=[]
            for item in root.findall('.//item'):
                try:
                    title=item.findtext('title') or '';stamp=parsedate_to_datetime(item.findtext('pubDate')).timestamp()
                    if not title or stamp>time.time()+60:continue
                    articles.append({'title':title,'timestamp':stamp,'url':item.findtext('link'),'sentiment':text_score(title),'source':key})
                except (ValueError,TypeError,AttributeError):continue
            if not articles:raise ValueError('no dated news')
            self.mark(key,True,f'{len(articles)} dated headlines; lexicon sentiment',200)
            return articles
        except Exception as e:self.mark(key,False,f'Invalid RSS payload: {e}');return []
    def collect_news(self,days):
        articles=[]
        try:articles+=self.parse_news('cointelegraph_rss',self.request('cointelegraph_rss','https://cointelegraph.com/rss'))
        except requests.RequestException:pass
        now=time.time()
        for symbol,name,_ in UNIVERSE:
            for offset in range(0,days,3):
                start=datetime.fromtimestamp(now-min(offset+3,days)*86400,timezone.utc).strftime('%Y-%m-%d')
                end=datetime.fromtimestamp(now-offset*86400+86400,timezone.utc).strftime('%Y-%m-%d')
                key=f'google_news:{symbol}'
                try:
                    response=self.request(key,'https://news.google.com/rss/search',{'q':f'{name} crypto after:{start} before:{end}','hl':'en-US','gl':'US','ceid':'US:en'})
                    articles+=self.parse_news(key,response)
                except requests.RequestException:pass
                time.sleep(.1)
        unique={a['title']:a for a in articles}
        return sorted(unique.values(),key=lambda a:(a['timestamp'],a['title']))
    def news(self):
        cached=self.cache.get('news')
        if cached and time.monotonic()-cached[0]<300:return cached[1]
        articles=self.collect_news(2)
        self.cache['news']=(time.monotonic(),articles)
        return articles
    def historical_news(self,days):
        return self.collect_news(days)
    def probe_binance(self):
        try:self.request('binance','https://api.binance.com/api/v3/klines',{'symbol':'BTCUSDT','interval':'5m','limit':30})
        except requests.RequestException:pass
