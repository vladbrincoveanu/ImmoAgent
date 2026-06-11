'use client';

import React from 'react';

export function ZoneVsAvgBadge({ pct, perM2Pct }: { pct: number | null | undefined; perM2Pct?: number | null }) {
  if (pct == null) return null;
  const good = pct <= -10;
  const meh = pct > -10 && pct < 10;
  const bad = pct >= 10;
  const cls = good ? 'bg-green-100 text-green-800' : meh ? 'bg-gray-100 text-gray-700' : 'bg-red-100 text-red-800';
  const sign = pct > 0 ? '+' : '';
  return (
    <span
      className={`text-[9px] font-semibold rounded px-1.5 py-0.5 ${cls}`}
      title={perM2Pct != null ? `${sign}${pct}% total price · ${sign}${perM2Pct}% €/m² vs zone avg` : `${sign}${pct}% vs zone avg price`}
    >
      {sign}{pct}% zone
    </span>
  );
}
