'use client';

interface TimeOnMarketBadgeProps {
  processedAt: number | null | undefined;
}

export function TimeOnMarketBadge({ processedAt }: TimeOnMarketBadgeProps) {
  if (!processedAt) return null;
  const ms = processedAt > 1e12 ? processedAt : processedAt * 1000;
  const ageMs = Date.now() - ms;
  const days = Math.floor(ageMs / (1000 * 60 * 60 * 24));

  let label: string;
  let cls: string;
  if (days < 0) {
    return null;
  } else if (days === 0) {
    label = 'fresh today';
    cls = 'bg-emerald-100 text-emerald-800';
  } else if (days < 3) {
    label = `${days}d old`;
    cls = 'bg-emerald-50 text-emerald-700';
  } else if (days < 7) {
    label = `${days}d on market`;
    cls = 'bg-blue-50 text-blue-700';
  } else if (days < 30) {
    label = `${days}d on market`;
    cls = 'bg-gray-100 text-gray-700';
  } else if (days < 90) {
    label = `${days}d on market`;
    cls = 'bg-yellow-50 text-yellow-800';
  } else {
    label = `${days}d stale`;
    cls = 'bg-red-50 text-red-800';
  }
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-[10px] font-medium rounded px-1.5 py-0.5 ${cls}`}
      data-testid="time-on-market-badge"
      data-days={days}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" /> {label}
    </span>
  );
}

interface PriceDropBadgeProps {
  priceHistory: Array<{ price_total?: number; date?: number }> | null | undefined;
  currentPrice: number | null | undefined;
}

export function PriceDropBadge({ priceHistory, currentPrice }: PriceDropBadgeProps) {
  if (!priceHistory || priceHistory.length < 1 || currentPrice == null) return null;
  const first = priceHistory[0];
  if (first.price_total == null) return null;
  if (first.price_total <= currentPrice) return null; // no drop
  const drop = first.price_total - currentPrice;
  const pct = Math.round((drop / first.price_total) * 100);
  if (pct < 1) return null;
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] font-semibold rounded px-1.5 py-0.5 bg-red-100 text-red-800"
      data-testid="price-drop-badge"
      data-drop-pct={pct}
      title={`Originally ${first.price_total.toLocaleString('de-AT')} €, now ${currentPrice.toLocaleString('de-AT')} €`}
    >
      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
      -{pct}%
    </span>
  );
}
