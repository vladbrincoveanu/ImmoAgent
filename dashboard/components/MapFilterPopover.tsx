'use client';

import { useState, useEffect } from 'react';

export interface MapFilterState {
  district: string;
  minScore: number;
  maxPrice: number;
  commuteTo: string;
  maxCommute: number;
}

interface MapFilterPopoverProps {
  open: boolean;
  onClose: () => void;
  initial: MapFilterState;
  onApply: (next: MapFilterState) => void;
}

const COMMUTE_OPTIONS = [
  { name: '', lat: '', lon: '' },
  { name: 'Stephansplatz',  lat: '48.2085', lon: '16.3726' },
  { name: 'Hauptbahnhof',   lat: '48.1855', lon: '16.3765' },
  { name: 'Donau City',     lat: '48.2376', lon: '16.4125' },
];

export const COMMUTE_COORDS: Record<string, { lat: string; lon: string }> = Object.fromEntries(
  COMMUTE_OPTIONS.filter((o) => o.name).map((o) => [o.name, { lat: o.lat, lon: o.lon }])
);

export function MapFilterPopover({ open, onClose, initial, onApply }: MapFilterPopoverProps) {
  const [district, setDistrict] = useState(initial.district);
  const [minScore, setMinScore] = useState(initial.minScore);
  const [maxPrice, setMaxPrice] = useState(initial.maxPrice);
  const [commuteTo, setCommuteTo] = useState(initial.commuteTo);
  const [maxCommute, setMaxCommute] = useState(initial.maxCommute || 45);

  useEffect(() => {
    if (open) {
      setDistrict(initial.district);
      setMinScore(initial.minScore);
      setMaxPrice(initial.maxPrice);
      setCommuteTo(initial.commuteTo);
      setMaxCommute(initial.maxCommute || 45);
    }
  }, [open, initial]);

  if (!open) return null;

  return (
    <div
      data-testid="filter-popover"
      className="absolute top-[52px] right-5 w-[280px] bg-card border border-line rounded-xl shadow-[0_12px_32px_rgba(22,36,58,0.14)] p-[18px] z-[1300]"
      onClick={(e) => e.stopPropagation()}
    >
      <label className="block text-[12px] font-semibold text-ink-2 mb-1.5">District</label>
      <input
        data-testid="filter-district"
        type="text"
        placeholder="e.g. 02"
        value={district}
        onChange={(e) => setDistrict(e.target.value)}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Min score</label>
      <input
        data-testid="filter-min-score"
        type="number"
        min={0}
        max={100}
        value={minScore}
        onChange={(e) => setMinScore(Number(e.target.value))}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Max price (€)</label>
      <input
        data-testid="filter-max-price"
        type="number"
        min={0}
        value={maxPrice}
        onChange={(e) => setMaxPrice(Number(e.target.value))}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Commute to</label>
      <select
        data-testid="filter-commute"
        value={commuteTo}
        onChange={(e) => setCommuteTo(e.target.value)}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      >
        {COMMUTE_OPTIONS.map((o) => (
          <option key={o.name} value={o.name}>
            {o.name || '— pick destination —'}
          </option>
        ))}
      </select>
      {commuteTo && (
        <>
          <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Max commute (min)</label>
          <input
            data-testid="filter-max-commute"
            type="number"
            min={5}
            max={120}
            step={5}
            value={maxCommute}
            onChange={(e) => setMaxCommute(Number(e.target.value))}
            className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
          />
        </>
      )}
      <button
        data-testid="filter-apply"
        onClick={() => {
          onApply({ district, minScore, maxPrice, commuteTo, maxCommute });
          onClose();
        }}
        className="w-full mt-4 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg"
      >
        Apply
      </button>
    </div>
  );
}
