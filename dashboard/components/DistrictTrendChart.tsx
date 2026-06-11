'use client';

import React, { useEffect, useState } from 'react';

interface MonthData {
  ym: string;
  avg_price: number;
  avg_price_per_m2: number;
  count: number;
}

interface DistrictTrendChartProps {
  bezirk: string;
}

export function DistrictTrendChart({ bezirk }: DistrictTrendChartProps) {
  const [data, setData] = useState<MonthData[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/district-trend/${encodeURIComponent(bezirk)}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setData(d.months ?? []); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [bezirk]);

  if (loading) return <div className="text-xs text-muted">Loading trend…</div>;
  if (!data || data.length < 2) return null;

  const maxPrice = Math.max(...data.map((m) => m.avg_price));
  const minPrice = Math.min(...data.map((m) => m.avg_price));
  const range = maxPrice - minPrice || 1;

  // Compute trend: compare first half vs second half
  const half = Math.floor(data.length / 2);
  const first = data.slice(0, half).reduce((s, m) => s + m.avg_price, 0) / half;
  const second = data.slice(half).reduce((s, m) => s + m.avg_price, 0) / (data.length - half);
  const trendPct = ((second - first) / first) * 100;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4" data-testid="district-trend-chart">
      <div className="flex items-baseline justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-800">District {bezirk} · 12-month price trend</h4>
        <span className={`text-xs font-medium ${trendPct > 0 ? 'text-red-600' : 'text-green-600'}`} data-testid="district-trend-pct">
          {trendPct > 0 ? '+' : ''}{trendPct.toFixed(1)}%
        </span>
      </div>
      <div className="flex items-end gap-1 h-20">
        {data.map((m) => {
          const h = ((m.avg_price - minPrice) / range) * 100;
          return (
            <div key={m.ym} className="flex-1 flex flex-col items-center" title={`${m.ym}: €${m.avg_price.toLocaleString('de-AT')} (n=${m.count})`}>
              <div
                className="w-full bg-blue-400 rounded-t min-h-[2px]"
                style={{ height: `${h}%` }}
                data-testid={`bar-${m.ym}`}
              />
              <p className="text-[8px] text-muted mt-0.5">{m.ym.slice(5)}</p>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-muted mt-1">
        Avg price per month from {data.length} months of listings
      </p>
    </div>
  );
}
