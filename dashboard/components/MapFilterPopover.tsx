'use client';

import { useState, useEffect } from 'react';

export interface MapFilterState {
  district: string;
  minScore: number;
  maxPrice: number;
  commuteTo: string;
}

interface MapFilterPopoverProps {
  open: boolean;
  onClose: () => void;
  initial: MapFilterState;
  onApply: (next: MapFilterState) => void;
}

const COMMUTE_OPTIONS = ['', 'Stephansplatz', 'Hauptbahnhof', 'Donau City'];

export function MapFilterPopover({ open, onClose, initial, onApply }: MapFilterPopoverProps) {
  const [district, setDistrict] = useState(initial.district);
  const [minScore, setMinScore] = useState(initial.minScore);
  const [maxPrice, setMaxPrice] = useState(initial.maxPrice);
  const [commuteTo, setCommuteTo] = useState(initial.commuteTo);

  useEffect(() => {
    if (open) {
      setDistrict(initial.district);
      setMinScore(initial.minScore);
      setMaxPrice(initial.maxPrice);
      setCommuteTo(initial.commuteTo);
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
          <option key={o} value={o}>
            {o || '— pick destination —'}
          </option>
        ))}
      </select>
      <button
        data-testid="filter-apply"
        onClick={() => {
          onApply({ district, minScore, maxPrice, commuteTo });
          onClose();
        }}
        className="w-full mt-4 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg"
      >
        Apply
      </button>
    </div>
  );
}
