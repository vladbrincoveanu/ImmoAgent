'use client';

import React, { useEffect, useState } from 'react';

interface Destination {
  name: string;
  lat: number;
  lon: number;
  category: string;
}

interface CommuteFilterProps {
  destName?: string;
  maxCommute?: string;
  onDestChange?: (name: string, lat: string, lon: string) => void;
  onMaxChange?: (v: string) => void;
}

export function CommuteFilter({
  destName = '',
  maxCommute = '',
  onDestChange,
  onMaxChange,
}: CommuteFilterProps = {}) {
  const [destinations, setDestinations] = useState<Destination[]>([]);

  useEffect(() => {
    fetch('/api/destinations')
      .then((r) => r.json())
      .then((d) => setDestinations(d.destinations ?? []))
      .catch(() => {});
  }, []);

  const handleDestChange = (name: string) => {
    if (!onDestChange) return;
    if (!name) {
      onDestChange('', '', '');
      return;
    }
    const dest = destinations.find((d) => d.name === name);
    onDestChange(name, dest ? String(dest.lat) : '', dest ? String(dest.lon) : '');
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
            value={maxCommute}
            onChange={(e) => onMaxChange?.(e.target.value)}
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
