interface EquityBadgeProps {
  downPct: number | null | undefined;
  downPctKimv: number | null | undefined;
  equityEur: number | null | undefined;
  confidence: string | null | undefined;
}

export function EquityBadge({ downPct, downPctKimv, equityEur, confidence }: EquityBadgeProps) {
  if (downPct == null) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-gray-500 bg-gray-100">
        ? equity
      </span>
    );
  }

  const pctRounded = Math.round(downPct);
  const eurK = equityEur != null ? Math.round(equityEur / 1000) : null;
  const label = eurK != null ? `~${pctRounded}% (~€${eurK}k)` : `~${pctRounded}%`;
  const isLowConfidence = confidence === 'low';

  let colorClass: string;
  if (downPctKimv != null && downPctKimv <= 15) {
    colorClass = isLowConfidence
      ? 'text-yellow-800 bg-yellow-50 border border-yellow-300'
      : 'text-green-800 bg-green-100';
  } else if (downPct <= 25) {
    colorClass = 'text-yellow-800 bg-yellow-100';
  } else {
    colorClass = 'text-orange-800 bg-orange-100';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}
      title={isLowConfidence ? 'Low confidence — some bank inputs missing' : undefined}
    >
      <span>{label}</span>
      {isLowConfidence && <span className="text-[10px] opacity-70">~</span>}
    </span>
  );
}
