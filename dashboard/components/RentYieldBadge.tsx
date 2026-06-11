'use client';

import React from 'react';

interface RentYieldBadgeProps {
  area_m2: number | null | undefined;
  price_total: number | null | undefined;
  bezirk: string | null | undefined;
}

const RENT_PER_M2: Record<string, number> = {
  '1010': 26, '1020': 20, '1030': 19, '1040': 19, '1050': 18, '1060': 18, '1070': 19,
  '1080': 19, '1090': 20, '1100': 16, '1110': 14, '1120': 15, '1130': 17, '1140': 15,
  '1150': 15, '1160': 15, '1170': 16, '1180': 17, '1190': 17, '1200': 16, '1210': 13,
  '1220': 13, '1230': 12,
};
const DEFAULT_RPM2 = 15;

export function RentYieldBadge({ area_m2, price_total, bezirk }: RentYieldBadgeProps) {
  if (!area_m2 || !price_total) return null;
  const rpm2 = (bezirk && RENT_PER_M2[bezirk]) || DEFAULT_RPM2;
  const monthly = Math.round(area_m2 * rpm2);
  const annual = monthly * 12;
  const yieldPct = Math.round((annual / price_total) * 1000) / 10;

  let cls = 'bg-gray-100 text-gray-700';
  let label = 'flat yield';
  if (yieldPct >= 4.5) { cls = 'bg-green-100 text-green-800'; label = 'good yield'; }
  else if (yieldPct >= 3.5) { cls = 'bg-emerald-100 text-emerald-800'; label = 'fair yield'; }
  else if (yieldPct < 2.5) { cls = 'bg-red-100 text-red-800'; label = 'low yield'; }

  return (
    <span
      className={`inline-flex items-center gap-0.5 text-[10px] font-semibold rounded px-1.5 py-0.5 ${cls}`}
      title={`Estimated gross yield: ${yieldPct}% · ~€${monthly}/mo rent · ~€${rpm2}/m² in ${bezirk ?? 'Vienna'}`}
      data-testid="rent-yield-badge"
    >
      {yieldPct}% yield · €{monthly}/mo
    </span>
  );
}
