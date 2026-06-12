'use client';

import React from 'react';

interface HeatPoint {
  lat: number;
  lon: number;
  weight: number;
}

interface PriceHeatmapProps {
  show: boolean;
  points: HeatPoint[];
}

export function PriceHeatmap({ show, points }: PriceHeatmapProps) {
  if (!show || points.length === 0) return null;
  return (
    <div
      className="absolute inset-0 pointer-events-none z-[900]"
      data-testid="price-heatmap"
    >
      <svg width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {points.map((p, i) => {
          const r = 25 + p.weight * 60;
          const o = 0.15 + p.weight * 0.35;
          const hue = 220 - 220 * p.weight;
          return (
            <circle
              key={i}
              cx={`${p.lat}%`}
              cy={`100% - ${p.lon}%`}
              r={r}
              fill={`hsl(${hue}, 70%, 50%)`}
              opacity={o}
            />
          );
        })}
      </svg>
    </div>
  );
}
