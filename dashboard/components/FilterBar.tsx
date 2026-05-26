'use client';

import React from 'react';

const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'price_asc', label: 'Price (low to high)' },
  { value: 'price_desc', label: 'Price (high to low)' },
  { value: 'date_desc', label: 'Newest first' },
  { value: 'area_desc', label: 'Largest first' },
] as const;

export type SortOption = typeof SORT_OPTIONS[number]['value'];

interface FilterBarProps {
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy?: SortOption;
  onSortChange?: (sort: SortOption) => void;
  maxPrice?: string;
  onMaxPriceChange?: (v: string) => void;
  showUnfinanceable?: boolean;
  onShowUnfinanceableChange?: (v: boolean) => void;
  equity?: string;
  onEquityChange?: (v: string) => void;
  rate?: string;
  onRateChange?: (v: string) => void;
}

export function FilterBar({
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh, sortBy, onSortChange,
  maxPrice, onMaxPriceChange,
  showUnfinanceable, onShowUnfinanceableChange,
  equity, onEquityChange,
  rate, onRateChange,
}: FilterBarProps) {
  const effectiveSort = sortBy ?? 'score_desc';

  return (
    <div className="hidden md:flex flex-wrap gap-3 mb-6 items-center">
      <div className="flex items-center gap-2 ml-auto">
        <label className="text-sm font-medium text-gray-700">Min Score</label>
        <input
          type="number" min="0" max="100" value={minScore}
          onChange={(e) => onMinScoreChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {maxPrice != null && onMaxPriceChange && (
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Max Price EUR</label>
          <input
            type="number" min="0" step="10000" value={maxPrice}
            onChange={(e) => onMaxPriceChange(e.target.value)}
            className="w-28 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">District</label>
        <input
          type="text" placeholder="e.g. 02" value={district}
          onChange={(e) => onDistrictChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <button
        onClick={onRefresh}
        className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
      >
        Refresh
      </button>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Sort</label>
        <select
          value={effectiveSort}
          onChange={(e) => onSortChange?.(e.target.value as SortOption)}
          className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {showUnfinanceable != null && onShowUnfinanceableChange && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showUnfinanceable}
            onChange={(e) => onShowUnfinanceableChange(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700">Show unfinanceable</span>
        </label>
      )}

      {equity != null && onEquityChange && (
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Equity (EUR)</label>
          <input
            type="number" min="0" step="1000" value={equity}
            onChange={(e) => onEquityChange(e.target.value)}
            className="w-28 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      {rate != null && onRateChange && (
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Rate (%)</label>
          <input
            type="number" min="0" step="0.1" value={rate}
            onChange={(e) => onRateChange(e.target.value)}
            className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}
    </div>
  );
}
