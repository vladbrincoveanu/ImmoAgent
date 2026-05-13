interface EquityBadgeProps {
  downPct: number | null | undefined;
  equityEur: number | null | undefined;
  confidence: string | null | undefined;
}

export function EquityBadge({ downPct, equityEur, confidence }: EquityBadgeProps) {
  if (confidence === 'low') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-gray-500 bg-gray-100">
        ? equity
      </span>
    );
  }

  if (downPct == null) return null;

  const pctRounded = Math.round(downPct);
  const eurK = equityEur != null ? Math.round(equityEur / 1000) : null;
  const label = eurK != null ? `~${pctRounded}% (~€${eurK}k)` : `~${pctRounded}%`;

  let colorClass: string;
  if (downPct <= 15) {
    colorClass = 'text-green-800 bg-green-100';
  } else if (downPct <= 25) {
    colorClass = 'text-yellow-800 bg-yellow-100';
  } else {
    colorClass = 'text-orange-800 bg-orange-100';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
}
