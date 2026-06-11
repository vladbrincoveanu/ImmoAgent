'use client';

import React, { useEffect, useState } from 'react';

export function MapLegend() {
  const [counts, setCounts] = useState<{ ubahn: number; school: number } | null>(null);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/geo/infrastructure')
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        const features = d?.features ?? [];
        const ubahn = features.filter((f: { properties: { kind: string } }) => f.properties.kind === 'ubahn').length;
        const school = features.filter((f: { properties: { kind: string } }) => f.properties.kind === 'school').length;
        setCounts({ ubahn, school });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg z-[1100] text-xs" data-testid="map-legend">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-3 py-2 font-semibold text-left"
        aria-expanded={open}
      >
        <span>Legend</span>
        <span className="text-muted ml-2">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 flex flex-col gap-1.5 min-w-[200px]">
          <div className="border-t border-gray-100 pt-1.5">
            <p className="text-[10px] uppercase text-muted font-semibold mb-1">Listings (pin color)</p>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-sm transform rotate-45 bg-red-500"></div><span>Exact address</span></div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-sm transform rotate-45 bg-orange-500"></div><span>Landmark vicinity</span></div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-sm transform rotate-45 bg-blue-500"></div><span>District centroid</span></div>
          </div>
          <div className="border-t border-gray-100 pt-1.5">
            <p className="text-[10px] uppercase text-muted font-semibold mb-1">Infrastructure</p>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: '#1d4ed8' }}></div>
              <span>U-Bahn station</span>
              {counts && <span className="ml-auto text-muted">{counts.ubahn}</span>}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: '#16a34a' }}></div>
              <span>School</span>
              {counts && <span className="ml-auto text-muted">{counts.school}</span>}
            </div>
            <p className="text-[10px] text-muted mt-1">Click any dot for name &amp; district</p>
          </div>
        </div>
      )}
    </div>
  );
}
