'use client';

import React, { useEffect, useState } from 'react';

interface CommuteBadgeProps {
  lat: number | null | undefined;
  lon: number | null | undefined;
  destLat: number;
  destLon: number;
  destName: string;
}

const WALK_KMH = 4.8;
const TRAIN_KMH = 30;

function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const R = 6371;
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLon = (b.lon - a.lon) * Math.PI / 180;
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

function estimateWalkMin(km: number) { return Math.round((km / WALK_KMH) * 60); }

export function CommuteBadge({ lat, lon, destLat, destLon, destName }: CommuteBadgeProps) {
  const [data, setData] = useState<{ minutes: number; mode: 'transit' | 'walk' } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (lat == null || lon == null) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const url = `/api/commute?lat=${lat}&lon=${lon}&dest_lat=${destLat}&dest_lon=${destLon}&dest_name=${encodeURIComponent(destName)}`;
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.recommended) setData({ minutes: d.recommended.minutes, mode: d.recommended.mode });
        else if (d.walk) setData({ minutes: d.walk.minutes, mode: 'walk' });
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [lat, lon, destLat, destLon, destName]);

  if (lat == null || lon == null) return null;
  if (loading) {
    return <span className="text-[9px] text-muted">calc…</span>;
  }
  if (!data) return null;

  let cls = 'bg-yellow-50 text-yellow-800';
  if (data.minutes <= 15) cls = 'bg-green-100 text-green-800';
  else if (data.minutes <= 30) cls = 'bg-emerald-100 text-emerald-800';
  else if (data.minutes > 45) cls = 'bg-red-100 text-red-800';

  const modeIcon = data.mode === 'transit' ? 'U' : 'W';
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-[10px] font-semibold rounded px-1.5 py-0.5 ${cls}`}
      title={`~${data.minutes} min ${data.mode === 'transit' ? 'by U-Bahn' : 'walking'} to ${destName}`}
      data-testid="commute-badge"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" /> {data.minutes}m {modeIcon} {destName.split(/[()]/)[0].trim().slice(0, 12)}
    </span>
  );
}
