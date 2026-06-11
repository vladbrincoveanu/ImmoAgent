'use client';

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

interface Insights {
  total: number;
  visible: number;
  unfinanceable_count: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  avg_score: number | null;
  district_count: number;
  below_avg_count: number;
  good_transit_count: number;
  best_deal_pct: number;
}

function formatK(value: number | null): string {
  if (value == null) return '—';
  if (value >= 1000) return `€${Math.round(value / 1000)}k`;
  return `€${value}`;
}

export function SmartInsightsPanel() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/insights?${searchParams.toString()}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [searchParams]);

  if (loading || !data) {
    return <div className="text-xs text-muted">Loading insights…</div>;
  }

  const cards: Array<{ label: string; value: string; sub?: string; tone?: 'good' | 'neutral' | 'warn' }> = [
    { label: 'Listings', value: `${data.visible}`, sub: data.unfinanceable_count > 0 ? `${data.unfinanceable_count} unfinanceable` : undefined, tone: 'neutral' },
    { label: 'Avg Price', value: formatK(data.avg_price), tone: 'neutral' },
    { label: 'Avg €/m²', value: data.avg_price_per_m2 ? `€${data.avg_price_per_m2}` : '—', tone: 'neutral' },
    { label: 'Avg Score', value: data.avg_score != null ? `${data.avg_score}` : '—', tone: data.avg_score != null && data.avg_score >= 55 ? 'good' : 'neutral' },
    { label: 'Districts', value: `${data.district_count}`, sub: data.district_count > 1 ? 'in this view' : undefined, tone: 'neutral' },
    { label: 'Below zone avg', value: `${data.below_avg_count}`, sub: `${data.best_deal_pct}% of total`, tone: data.best_deal_pct >= 30 ? 'good' : 'neutral' },
    { label: 'U-Bahn ≤5 min', value: `${data.good_transit_count}`, tone: 'good' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 mb-4" data-testid="smart-insights">
      {cards.map((c) => (
        <div
          key={c.label}
          className={`rounded-lg border px-3 py-2 ${
            c.tone === 'good' ? 'border-green-200 bg-green-50' :
            c.tone === 'warn' ? 'border-yellow-200 bg-yellow-50' :
            'border-border bg-white'
          }`}
        >
          <p className="text-[10px] uppercase tracking-wide text-muted font-semibold">{c.label}</p>
          <p className="text-lg font-bold text-heading leading-tight">{c.value}</p>
          {c.sub && <p className="text-[10px] text-muted leading-tight">{c.sub}</p>}
        </div>
      ))}
    </div>
  );
}
