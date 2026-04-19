export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const displayScore = typeof score === 'number' ? score.toFixed(1) : score;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold text-white bg-accent">
      {displayScore}
    </span>
  );
}