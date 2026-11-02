'use client';

import * as React from 'react';
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent
} from '@/components/ui/chart';

export const description = 'Scan-history risk chart';

const chartConfig = {
  risk: {
    label: 'Mean risk',
    color: 'var(--primary)'
  },
  alerts: {
    label: 'Alerts',
    color: 'var(--muted-foreground)'
  }
} satisfies ChartConfig;

/** Legacy chart component. Overview uses EquityCurveGraph; keep this on the live history API. */
export function BarGraph() {
  const [activeChart, setActiveChart] =
    React.useState<keyof typeof chartConfig>('risk');
  const [chartData, setChartData] = React.useState<any[]>([]);
  const [isClient, setIsClient] = React.useState(false);

  React.useEffect(() => {
    setIsClient(true);
  }, []);

  React.useEffect(() => {
    if (!isClient) return;
    const fetchChartData = async () => {
      try {
        const res = await fetch('/api/backend/detection/history');
        if (!res.ok) throw new Error('history unavailable');
        const data = await res.json();
        setChartData(
          Array.isArray(data)
            ? data.map((row: any) => ({
                timestamp: row.time,
                risk: row.coverage ? row.risk * 100 : 0,
                alerts: row.alerts ?? 0
              }))
            : []
        );
      } catch {
        setChartData([]);
      }
    };
    fetchChartData();
    const interval = setInterval(fetchChartData, 60000);
    return () => clearInterval(interval);
  }, [isClient]);

  if (!isClient) return null;

  return (
    <Card className='@container/card !pt-3'>
      <CardHeader className='flex flex-col items-stretch space-y-0 border-b !p-0 sm:flex-row'>
        <div className='flex flex-1 flex-col justify-center gap-1 px-6 !py-0'>
          <CardTitle>Live Market Metrics</CardTitle>
          <CardDescription>
            Mean experimental risk from automatic scans
          </CardDescription>
        </div>
        <div className='flex'>
          {(['risk', 'alerts'] as const).map((key) => (
            <button
              key={key}
              data-active={activeChart === key}
              className='data-[active=true]:bg-muted/50 relative z-30 flex flex-1 flex-col justify-center gap-1 border-t px-6 py-4 text-left even:border-l sm:border-t-0 sm:border-l sm:px-8 sm:py-6'
              onClick={() => setActiveChart(key)}
            >
              <span className='text-muted-foreground text-xs'>
                {chartConfig[key].label}
              </span>
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className='px-2 sm:p-6'>
        {chartData.length === 0 ? (
          <p className='text-muted-foreground py-16 text-center text-sm'>
            No scan history yet.
          </p>
        ) : (
          <ChartContainer
            config={chartConfig}
            className='aspect-auto h-[250px] w-full'
          >
            <LineChart data={chartData} margin={{ left: 12, right: 12 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey='timestamp'
                tickFormatter={(v) =>
                  new Date(v).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                }
                minTickGap={32}
              />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Line
                dataKey={activeChart}
                type='linear'
                stroke={`var(--color-${activeChart})`}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
