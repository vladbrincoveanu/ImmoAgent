'use client';

import React from 'react';

const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'price_asc', label: 'Price (low to high)' },
  { value: 'price_desc', label: 'Price (high to low)' },
  { value: 'date_desc', label: 'Newest first' },
  { value: 'area_desc', label: 'Largest first' },
] as const;

type SortOption = typeof SORT_OPTIONS[number]['value'];

interface FilterBarProps {
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
}

export function FilterBar({
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh, sortBy, onSortChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <div className="flex items-center gap-2 ml-auto">
        <label className="text-sm font-medium text-gray-700">Min Score</label>
        <input
          type="number"
          min="0"
          max="100"
          value={minScore}
          onChange={(e) => onMinScoreChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">District</label>
        <input
          type="text"
          placeholder="e.g. 02"
          value={district}
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
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}