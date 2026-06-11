'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';

interface Destination {
  name: string;
  lat: number;
  lon: number;
  category: string;
}

export function CommuteFilter() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [destName, setDestName] = useState<string>(searchParams.get('dest_name') ?? '');
  const [maxMinutes, setMaxMinutes] = useState<string>(searchParams.get('max_commute') ?? '');

  useEffect(() => {
    fetch('/api/destinations')
      .then((r) => r.json())
      .then((d) => setDestinations(d.destinations ?? []))
      .catch(() => {});
  }, []);

  // Sync from URL on change
  useEffect(() => {
    setDestName(searchParams.get('dest_name') ?? '');
    setMaxMinutes(searchParams.get('max_commute') ?? '');
  }, [searchParams]);

  const updateUrl = (next: { dest_name?: string; dest_lat?: string; dest_lon?: string; max_commute?: string }) => {
    const params = new URLSearchParams(searchParams.toString());
    if (next.dest_name !== undefined) {
      if (next.dest_name) {
        params.set('dest_name', next.dest_name);
        const dest = destinations.find((d) => d.name === next.dest_name);
        if (dest) {
          params.set('dest_lat', String(dest.lat));
          params.set('dest_lon', String(dest.lon));
        }
      } else {
        params.delete('dest_name');
        params.delete('dest_lat');
        params.delete('dest_lon');
      }
    }
    if (next.max_commute !== undefined) {
      if (next.max_commute) params.set('max_commute', next.max_commute);
      else params.delete('max_commute');
    }
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  const handleDestChange = (name: string) => {
    setDestName(name);
    updateUrl({ dest_name: name });
  };

  const handleMaxChange = (v: string) => {
    setMaxMinutes(v);
    updateUrl({ max_commute: v });
  };

  return (
    <div className="flex items-center gap-2" data-testid="commute-filter">
      <label className="text-sm font-medium text-gray-700">Commute to</label>
      <select
        value={destName}
        onChange={(e) => handleDestChange(e.target.value)}
        className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700 min-w-[180px]"
        data-testid="commute-destination"
      >
        <option value="">— pick destination —</option>
        {destinations.map((d) => (
          <option key={d.name} value={d.name}>{d.name}</option>
        ))}
      </select>
      {destName && (
        <>
          <label className="text-sm font-medium text-gray-700">≤</label>
          <input
            type="number" min="5" max="120" step="5" placeholder="45"
            value={maxMinutes}
            onChange={(e) => handleMaxChange(e.target.value)}
            className="w-16 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="commute-max"
            title="Max commute minutes (straight-line walk estimate)"
          />
          <span className="text-xs text-muted">min</span>
        </>
      )}
    </div>
  );
}
