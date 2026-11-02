'use client';
import React, { useEffect, useState } from 'react';
import PageContainer from '@/components/layout/page-container';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { EquityCurveGraph } from '@/features/overview/components/area-graph';

type Coin={id:string;symbol:string;name:string;image?:string;current_price:number|null;market_cap:number|null;price_change_percentage_24h:number|null;flag:string;manipulation_score:number|null;pump_score:number|null;dump_score:number|null;data_status:string;series_source:string;age_seconds:number;news_status?:string;sentiment_count?:number;reason?:string;engine:string;};
type Provider={status:string;detail:string;http_status:number|null;checked_at:string};
type Health={apis:Record<string,Provider>;engine:{cpp_loaded:boolean;lock_free:boolean};running:boolean;interval_sec:number;last_scan_at:string|null;last_error:string|null;dataset_id:string|null;active_model:{artifact:string;heldout:{macro_f1:number;accuracy:number;always_normal_macro_f1?:number;beats_always_normal?:boolean};label_kind:string}|null;};
const flagClass=(flag:string)=>flag==='pump'?'bg-emerald-500/15 text-emerald-600':flag==='dump'?'bg-rose-500/15 text-rose-600':flag==='watch'?'bg-amber-500/15 text-amber-600':'bg-muted text-muted-foreground';
const money=(n:number|null)=>n==null?'—':n.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:n<1?6:2});
export default function OverViewLayout(_: {pie_stats:React.ReactNode;bar_stats:React.ReactNode;area_stats:React.ReactNode}) {
  const [coins,setCoins]=useState<Coin[]>([]);const [health,setHealth]=useState<Health|null>(null);
  const [stats,setStats]=useState<Record<string,number>|null>(null);const [error,setError]=useState<string|null>(null);const [search,setSearch]=useState('');
  useEffect(()=>{let alive=true;const refresh=async()=>{try{
    const responses=await Promise.all(['/coins','/detection/health','/dashboard'].map(p=>fetch('/api/backend'+p)));
    if(responses.some(r=>!r.ok))throw Error('API unavailable — check the backend on port 8000.');
    const [c,h,d]=await Promise.all(responses.map(r=>r.json()));if(alive){setCoins(c);setHealth(h);setStats(d.stats);setError(null);}
  }catch(e){if(alive){setError(e instanceof Error?e.message:'API unavailable');setCoins([]);setStats(null);setHealth(null);}}};refresh();const t=setInterval(refresh,10000);return()=>{alive=false;clearInterval(t);};},[]);
  const filtered=coins.filter(c=>(c.name+' '+c.symbol).toLowerCase().includes(search.toLowerCase()));
  const alerts=coins.filter(c=>['pump','dump','watch'].includes(c.flag));
  const cards=[['Coins Scanned',stats?.coins_scanned,'Fresh windows scored by the active model'],['Pump/Dump Flags',stats?.flagged_windows,'Directional alerts only (excludes watch)'],['Watch Windows',stats?.watch_windows ?? stats?.alert_windows,'Elevated risk below the pump/dump threshold'],['Mean Risk',stats?`${(stats.avg_risk*100).toFixed(1)}%`:undefined,'Uncalibrated model score across fresh coins']];
  return <PageContainer><div className='flex min-w-0 flex-1 flex-col space-y-4'>
    <div className='flex flex-col gap-2'><h2 className='text-2xl font-bold tracking-tight'>Manipulation Detection Overview</h2><p className='text-muted-foreground text-sm'>Sentiment, cross-coin correlation and volatility · next 15-minute anomaly risk</p>
      <div className='flex flex-wrap items-center gap-2 text-xs'><Badge variant='outline'>{health?.running?'Auto-scan active':'Scanner unavailable'}</Badge><Badge variant='outline'>{health?.engine.cpp_loaded?'C++ scoring':'Native engine unavailable / Python fallback'}</Badge><span className='text-muted-foreground'>Last scan: {health?.last_scan_at?new Date(health.last_scan_at).toLocaleTimeString():'waiting'}</span><a href='http://127.0.0.1:8000/docs' target='_blank' rel='noreferrer' className='underline'>API docs :8000</a></div>
    </div>
    {error&&<p role='alert' className='border-destructive/40 bg-destructive/10 text-destructive rounded-md border p-3 text-sm'>{error}</p>}
    <div className='bg-muted/50 text-muted-foreground rounded-md border p-3 text-xs'>Research baseline: trained on weak labels for abnormal price moves, not confirmed manipulation. Scores are uncalibrated. News uses dated headlines; missing sentiment is explicitly marked. {health?.active_model?`Active model ${health.active_model.artifact.slice(0,12)} · held-out macro F1 ${health.active_model.heldout.macro_f1.toFixed(3)}.`:'No model promoted yet — train in the Detection Lab.'}</div>
    {health?.active_model?.heldout.beats_always_normal === false && <p className='rounded-md border border-amber-600/40 bg-amber-500/10 p-3 text-xs text-amber-500'>Validation limitation: held-out macro F1 {health.active_model.heldout.macro_f1.toFixed(3)} is below the always-normal baseline {health.active_model.heldout.always_normal_macro_f1?.toFixed(3)}. Treat all flags as research signals, not reliable forecasts.</p>}
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-7'>
      <div className='min-w-0 md:col-span-2 lg:col-span-4'><EquityCurveGraph/></div>
      <div className='min-w-0 md:col-span-2 lg:col-span-3'>
        <h3 className='mb-2 text-xl font-semibold'>Monitored Coins</h3>
        {alerts.length>0&&<div className='mb-3 flex flex-wrap gap-2'>{alerts.slice(0,6).map(c=><span key={c.id} className={`rounded px-2 py-1 text-xs font-medium uppercase ${flagClass(c.flag)}`}>{c.symbol} {c.flag==='watch'?'watch':`possible ${c.flag}`} · {((c.manipulation_score||0)*100).toFixed(0)}%</span>)}</div>}
        <input aria-label='Search coins' className='bg-background mb-4 w-full rounded-md border px-3 py-2' placeholder='Search by name or symbol…' value={search} onChange={e=>setSearch(e.target.value)}/>
        <div className='max-h-[380px] overflow-auto rounded-lg border'><table className='w-full text-sm'><thead className='bg-muted sticky top-0'><tr><th className='p-3 text-left'>Coin</th><th className='p-3 text-right'>Price</th><th className='p-3 text-right'>24h</th><th className='p-3 text-right'>Risk / Flag</th></tr></thead><tbody>
          {filtered.map(c=><tr key={c.id} className='hover:bg-muted/40 border-t'><td className='p-3'><div className='flex items-center gap-2'>{c.image&&<img alt='' src={c.image} className='h-6 w-6'/>}<div><div className='font-medium'>{c.symbol}</div><div className='text-muted-foreground text-xs'>{c.name}</div></div></div></td><td className='p-3 text-right tabular-nums'>{money(c.current_price)}<div className='text-muted-foreground text-xs'>{c.data_status==='stale'?'Stale':c.series_source+' · 5m'}</div></td><td className='p-3 text-right tabular-nums'>{c.price_change_percentage_24h==null?'—':`${c.price_change_percentage_24h.toFixed(2)}%`}</td><td className='p-3 text-right'><span title={c.reason||'Experimental next-15-minute anomaly signal'} className={`whitespace-nowrap rounded px-2 py-1 text-xs ${flagClass(c.flag)}`}>{c.flag==='pump'||c.flag==='dump'?`Possible ${c.flag}`:c.flag}</span><div className='mt-1 text-xs tabular-nums'>{c.manipulation_score==null?'Not scored':`${(c.manipulation_score*100).toFixed(1)} / 100 score`}</div><div className='text-muted-foreground mt-1 text-[10px]'>{c.news_status==='covered'?`${c.sentiment_count} headlines`:'No matching news'}</div></td></tr>)}
          {!filtered.length&&<tr><td colSpan={4} className='text-muted-foreground p-8 text-center'>{search?'No matching coins.':'Waiting for the first automatic scan.'}</td></tr>}
        </tbody></table></div>
        <p className='text-muted-foreground mt-2 text-xs'>8 liquid USD markets · scans every {health?.interval_sec||60}s · observations older than 10 minutes cannot trigger alerts.</p>
      </div>
    </div>
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4'>{cards.map(([title,value,description])=><Card key={title} className='@container/card'><CardHeader><CardDescription>{title}</CardDescription><CardTitle className='text-2xl font-semibold tabular-nums'>{value??'—'}</CardTitle><p className='text-muted-foreground text-xs'>{description}</p></CardHeader></Card>)}</div>
    <Card><CardHeader><CardTitle>Data Sources &amp; Health</CardTitle><CardDescription>Live request outcomes. Missing feeds remain visible; no synthetic market fallback.</CardDescription></CardHeader><CardContent>
      <div className='grid gap-3 md:grid-cols-2'>{Object.entries(health?.apis||{}).map(([name,p])=><div key={name} className='rounded border p-3 text-xs'><div className='mb-1 flex justify-between gap-2'><span className='font-medium'>{name}</span><Badge variant='outline' className={p.status==='working'?'text-emerald-600':'text-amber-600'}>{p.status}{p.http_status?` · ${p.http_status}`:''}</Badge></div><p className='text-muted-foreground break-words'>{p.detail}</p><p className='text-muted-foreground mt-1'>Checked {new Date(p.checked_at).toLocaleTimeString()}</p></div>)}</div>
      <p className='text-muted-foreground mt-4 text-xs'>Coinbase supplies 5m candles; CoinGecko supplies optional market metadata. Cointelegraph and dated Google News RSS supply headline sentiment. Binance is probed for transparency but is not the active feed. TimescaleDB is disabled; scan history and jobs use local SQLite. Clerk keys are not required.</p>
      {health?.last_error&&<p className='text-destructive mt-2 text-xs'>{health.last_error}</p>}
    </CardContent></Card>
  </div></PageContainer>;
}
