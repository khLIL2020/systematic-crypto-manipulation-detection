'use client';
import { useEffect, useState } from 'react';
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
export function EquityCurveGraph() {
  const [data,setData]=useState<{time:string;risk:number;coverage:number;alerts:number}[]>([]);
  const [error,setError]=useState(false);
  useEffect(()=>{let alive=true;const refresh=async()=>{try{const r=await fetch('/api/backend/detection/history');if(!r.ok)throw Error();const rows=await r.json();if(alive){setData(rows);setError(false);}}catch{if(alive)setError(true);}};refresh();const t=setInterval(refresh,15000);return()=>{alive=false;clearInterval(t);};},[]);
  return <Card className='@container/card'>
    <CardHeader><CardTitle>Manipulation Risk Monitor</CardTitle><CardDescription>Observed model risk across monitored coins · automatic 60-second scans</CardDescription></CardHeader>
    <CardContent>
      {error ? <p className='text-destructive py-16 text-sm'>Scan history unavailable. Check the API connection.</p> : data.some(d=>d.coverage>0) ?
      <ChartContainer config={{risk:{label:'Mean risk',color:'var(--primary)'}}} className='h-[300px] w-full'>
        <AreaChart data={data.map(d=>({...d,risk:d.coverage?d.risk*100:null}))} margin={{left:0,right:12,top:12,bottom:8}}>
          <defs><linearGradient id='fillRisk' x1='0' y1='0' x2='0' y2='1'><stop offset='5%' stopColor='var(--primary)' stopOpacity={.5}/><stop offset='95%' stopColor='var(--primary)' stopOpacity={.03}/></linearGradient></defs>
          <CartesianGrid vertical={false}/><XAxis dataKey='time' tickFormatter={v=>new Date(v).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})} minTickGap={40}/><YAxis domain={[0,100]} tickFormatter={v=>`${v}%`}/>
          <ChartTooltip content={<ChartTooltipContent labelFormatter={v=>new Date(v).toLocaleString()}/>}/><Area type='linear' dataKey='risk' stroke='var(--primary)' fill='url(#fillRisk)' connectNulls={false}/>
        </AreaChart>
      </ChartContainer> : <div className='text-muted-foreground flex h-[300px] items-center justify-center text-sm'>Waiting for fresh scans and a trained model. No demo values.</div>}
    </CardContent><CardFooter className='text-muted-foreground text-xs'>Experimental anomaly scores, not calibrated probabilities of manipulation. Gaps indicate missing coverage.</CardFooter>
  </Card>;
}

export const AreaGraph = EquityCurveGraph;
