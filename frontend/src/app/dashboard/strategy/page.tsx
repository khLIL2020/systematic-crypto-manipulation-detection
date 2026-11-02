'use client';

import React, { useCallback, useEffect, useState } from 'react';
import PageContainer from '@/components/layout/page-container';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger
} from '@/components/ui/tabs';

type JobKind = 'train' | 'replay' | 'score' | 'ingest';
type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

type DetectionJob = {
  id: string;
  kind: JobKind;
  symbol: string;
  seed: number;
  artifact_id?: string;
  dataset_id?: string;
  model_id?: string;
  threads: number;
  notes: string;
  config_hash: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  runtime_seconds: number | null;
  metrics: Record<string, number | string> | null;
  error: string | null;
};

type SignalSnapshot = {
  symbol: string;
  as_of: string;
  reason?: string;
  signals: {
    sentiment: number;
    price_correlation: number;
    volatility: number;
  };
  manipulation_score: number | null;
  risk_band: string;
  model: {
    name: string;
    features: string[];
  };
};

const API = '/api/backend';

export default function DetectionLabPage() {
  const [jobs, setJobs] = useState<DetectionJob[]>([]);
  const [signals, setSignals] = useState<SignalSnapshot | null>(null);
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [kind, setKind] = useState<JobKind>('train');
  const [seed, setSeed] = useState(42);
  const [threads, setThreads] = useState(8);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [jobsRes, signalsRes] = await Promise.all([
        fetch(`${API}/detection/jobs`),
        fetch(`${API}/detection/signals?symbol=${encodeURIComponent(symbol)}`)
      ]);
      if (!jobsRes.ok) {
        throw new Error('Detection API unavailable');
      }
      setJobs(await jobsRes.json());
      setSignals(signalsRes.ok ? await signalsRes.json() : null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load detection data');
    }
  }, [symbol]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2500);
    return () => clearInterval(id);
  }, [refresh]);

  const enqueue = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/detection/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind,
          symbol,
          seed,
          epochs: 350,
          threads,
          notes:
            notes ||
            `${kind} run for ${symbol} with ${threads}-thread lock-free replay pool`
        })
      });
      if (!res.ok) throw new Error('Failed to enqueue job');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Enqueue failed');
    } finally {
      setBusy(false);
    }
  };

  const jobAction = async (id: string, action: 'rerun' | 'promote') => {
    try {
      const path = action === 'rerun' ? `/detection/jobs/${id}/rerun` : `/detection/models/promote/${id}`;
      const r = await fetch(API + path, {method: 'POST'});
      if (!r.ok) throw Error(await r.text());
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Action failed'); }
  };

  return (
    <PageContainer>
      <div className='flex min-w-0 flex-1 flex-col space-y-6'>
        <div className='space-y-1'>
          <h1 className='text-2xl font-bold tracking-tight'>Detection Lab</h1>
          <p className='text-muted-foreground max-w-3xl text-sm'>
            Train and score a manipulation detector on fused sentiment,
            price-correlation, and volatility features. Experiment jobs stay
            reproducible through saved datasets, model artifacts, config hashes and seeds.
            Weak price-anomaly labels are not verified manipulation; scores are experimental.
          </p>
        </div>

        {error && (
          <div className='border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-3 py-2 text-sm'>
            {error}
          </div>
        )}

        <div className='grid grid-cols-1 gap-4 lg:grid-cols-3'>
          <Card className='lg:col-span-1'>
            <CardHeader>
              <CardTitle>Live signal blend</CardTitle>
              <CardDescription>
                Online features feeding the manipulation score
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              {signals ? (
                <>
                  <div className='flex items-center justify-between'>
                    <span className='text-sm font-medium'>{signals.symbol}</span>
                    <Badge variant='outline' className='capitalize'>
                      {signals.risk_band}
                    </Badge>
                  </div>
                  <div className='text-3xl font-semibold tabular-nums'>
                    {signals.manipulation_score == null ? 'Unavailable' : signals.manipulation_score.toFixed(3)}
                  </div>
                  <div className='space-y-2 text-sm'>
                    <SignalRow
                      label='Sentiment'
                      value={signals.signals.sentiment ?? 0}
                    />
                    <SignalRow
                      label='Price correlation'
                      value={signals.signals.price_correlation ?? 0}
                    />
                    <SignalRow
                      label='Volatility'
                      value={signals.signals.volatility ?? 0}
                    />
                  </div>
                  <p className='text-muted-foreground text-xs'>
                    Model {signals.model.name} · as of{' '}
                    {new Date(signals.as_of).toLocaleTimeString()}
                  </p>
                </>
              ) : (
                <p className='text-muted-foreground text-sm'>No fresh signal yet for this symbol.</p>
              )}
            </CardContent>
          </Card>

          <Card className='lg:col-span-2'>
            <CardHeader>
              <CardTitle>Enqueue experiment</CardTitle>
              <CardDescription>
                Orchestrate train, parallel C++ replay, or online score jobs
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              <Tabs value={kind} onValueChange={(v) => setKind(v as JobKind)}>
                <TabsList>
                  <TabsTrigger value='train'>Train</TabsTrigger>
                  <TabsTrigger value='replay'>Replay</TabsTrigger>
                  <TabsTrigger value='score'>Score</TabsTrigger>
                  <TabsTrigger value='ingest'>Collect data</TabsTrigger>
                </TabsList>
                <TabsContent value={kind} className='mt-4 space-y-4'>
                  <div className='grid grid-cols-1 gap-4 md:grid-cols-3'>
                    <div className='space-y-1'>
                      <label className='text-sm font-medium'>Symbol</label>
                      <Input
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value)}
                      />
                    </div>
                    <div className='space-y-1'>
                      <label className='text-sm font-medium'>Seed</label>
                      <Input
                        type='number'
                        value={seed}
                        onChange={(e) => setSeed(Number(e.target.value))}
                      />
                    </div>
                    <div className='space-y-1'>
                      <label className='text-sm font-medium'>
                        Replay threads ({threads})
                      </label>
                      <Slider
                        value={[threads]}
                        min={1}
                        max={16}
                        step={1}
                        onValueChange={(v) => setThreads(v[0])}
                      />
                    </div>
                  </div>
                  <div className='space-y-1'>
                    <label className='text-sm font-medium'>Notes</label>
                    <Input
                      placeholder='Optional run note for the audit trail'
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                  <p className='text-muted-foreground text-xs'>
                    Replay measures recorded feature windows using atomic work distribution
                    across std::thread workers. Timings below are measured; the historical
                    12 → 4 minute claim is unverified. Training uses the full recorded universe;
                    Symbol selects the live signal and recorded scoring target.
                  </p>
                  <Button onClick={enqueue} disabled={busy} className='w-full md:w-auto'>
                    {busy ? 'Submitting…' : `Enqueue ${kind} job`}
                  </Button>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Experiment ledger</CardTitle>
            <CardDescription>
              Traceable runs with config hash, seed, status, and metrics
            </CardDescription>
          </CardHeader>
          <CardContent className='overflow-x-auto'>
            <table className='w-full text-left text-sm'>
              <thead className='text-muted-foreground border-b'>
                <tr>
                  <th className='py-2 pr-3 font-medium'>Kind</th>
                  <th className='py-2 pr-3 font-medium'>Symbol</th>
                  <th className='py-2 pr-3 font-medium'>Status</th>
                  <th className='py-2 pr-3 font-medium'>Seed</th>
                  <th className='py-2 pr-3 font-medium'>Config</th>
                  <th className='py-2 pr-3 font-medium'>Runtime</th>
                  <th className='py-2 font-medium'>Metrics</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className='border-b last:border-0'>
                    <td className='py-2 pr-3 capitalize'>{job.kind}</td>
                    <td className='py-2 pr-3'>{job.symbol}</td>
                    <td className='py-2 pr-3'>
                      <Badge variant='outline' className='capitalize'>
                        {job.status}
                      </Badge>
                    </td>
                    <td className='py-2 pr-3 tabular-nums'>{job.seed}</td>
                    <td className='py-2 pr-3 font-mono text-xs'>
                      {job.config_hash.slice(0, 12)}
                    </td>
                    <td className='py-2 pr-3 tabular-nums'>
                      {job.runtime_seconds != null
                        ? `${job.runtime_seconds.toFixed(3)}s`
                        : '—'}
                    </td>
                    <td className='text-muted-foreground py-2 text-xs'>
                      {job.metrics
                        ? Object.entries(job.metrics)
                            .slice(0, 3)
                            .map(([k, v]) => `${k}=${typeof v === 'number' ? Number(v.toFixed(4)) : typeof v === 'object' ? JSON.stringify(v) : v}`)
                            .join(' · ')
                        : job.error || job.notes || '—'}
                      <div className="mt-2 flex flex-wrap gap-3">
                        {job.artifact_id && <a className="underline" href={`${API}/detection/artifacts/${job.artifact_id}`} target="_blank" rel="noreferrer">Artifact</a>}
                        <a className="underline" href={`${API}/detection/jobs/${job.id}`} target="_blank" rel="noreferrer">Full provenance</a>
                        {job.status === 'succeeded' && <button className="underline" onClick={() => jobAction(job.id, 'rerun')}>Reproduce run</button>}
                        {job.kind === 'train' && job.status === 'succeeded' && <button className="underline" onClick={() => jobAction(job.id, 'promote')}>Promote model</button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className='text-muted-foreground py-6 text-center'
                    >
                      No jobs yet. Enqueue a train or replay run.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}

function SignalRow({ label, value }: { label: string; value: number }) {
  return (
    <div className='space-y-1'>
      <div className='flex items-center justify-between'>
        <span>{label}</span>
        <span className='tabular-nums'>{value.toFixed(3)}</span>
      </div>
      <div className='bg-muted h-1.5 overflow-hidden rounded'>
        <div
          className='bg-foreground h-full rounded'
          style={{ width: `${Math.max(0, Math.min(100, Math.abs(value) * 100))}%` }}
        />
      </div>
    </div>
  );
}
