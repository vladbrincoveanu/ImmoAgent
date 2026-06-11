'use client';

import { useState } from 'react';

export function MapGuide() {
  const [open, setOpen] = useState(true);
  return (
    <div
      className="absolute top-4 right-4 z-[1100] bg-white rounded-lg shadow-lg text-xs"
      data-testid="map-guide"
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-3 py-2 font-semibold text-gray-800"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-1.447-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          Map guide
        </span>
        <span className="text-muted ml-2">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-3 pb-2.5 space-y-1.5 min-w-[180px]">
          <div className="flex items-center gap-2" data-testid="legend-price-pin">
            <span className="inline-block w-3 h-3 rounded-full bg-[#ef4444]"></span>
            <span>Price pin — tap to view</span>
          </div>
          <div className="flex items-center gap-2" data-testid="legend-ubahn">
            <span className="inline-block w-3 h-3 rounded-full bg-[#1d4ed8]"></span>
            <span>U-Bahn station — name shown</span>
          </div>
          <div className="flex items-center gap-2" data-testid="legend-school">
            <span className="inline-block w-3 h-3 rounded-full bg-[#16a34a]"></span>
            <span>School — hover for name</span>
          </div>
          <div className="text-[10px] text-muted pt-1 border-t border-gray-100">
            Pin color = location precision
            <br />Red: exact · Orange: landmark · Blue: district
          </div>
        </div>
      )}
    </div>
  );
}
