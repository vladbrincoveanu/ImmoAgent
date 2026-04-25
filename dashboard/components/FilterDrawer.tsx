'use client';

import React, { useState, useEffect } from 'react';
import { SortOption } from './FilterBar';

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
}

export function FilterDrawer({
  open,
  onClose,
  minScore,
  onMinScoreChange,
  district,
  onDistrictChange,
  onRefresh,
  sortBy,
  onSortChange,
}: FilterDrawerProps) {
  const [localMinScore, setLocalMinScore] = useState(minScore);
  const [localDistrict, setLocalDistrict] = useState(district);
  const [localSortBy, setLocalSortBy] = useState(sortBy);

  useEffect(() => {
    setLocalMinScore(minScore);
    setLocalDistrict(district);
    setLocalSortBy(sortBy);
  }, [minScore, district, sortBy]);

  if (!open) return null;

  const handleApply = () => {
    onMinScoreChange(localMinScore);
    onDistrictChange(localDistrict);
    onSortChange(localSortBy);
    onRefresh();
    onClose();
  };

  const handleReset = () => {
    setLocalMinScore('0');
    setLocalDistrict('');
    setLocalSortBy('score_desc');
  };

  return (
    <div className="fixed inset-0 z-[200] flex flex-col">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      <div className="relative mt-auto bg-white rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.1)] flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-lg font-semibold text-heading">Filters</h2>
          <button
            onClick={onClose}
            className="w-11 h-11 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            aria-label="Close filters"
          >
            <svg className="w-5 h-5 text-text" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Minimum Score</label>
            <input
              type="number"
              min="0"
              max="100"
              value={localMinScore}
              onChange={(e) => setLocalMinScore(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">District</label>
            <input
              type="text"
              placeholder="e.g. 02"
              value={localDistrict}
              onChange={(e) => setLocalDistrict(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Sort By</label>
            <select
              value={localSortBy}
              onChange={(e) => setLocalSortBy(e.target.value as SortOption)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="score_desc">Score (high to low)</option>
              <option value="price_asc">Price (low to high)</option>
              <option value="price_desc">Price (high to low)</option>
              <option value="date_desc">Newest first</option>
              <option value="area_desc">Largest first</option>
            </select>
          </div>
        </div>

        <div className="flex gap-3 px-5 py-4 border-t border-border shrink-0">
          <button
            onClick={handleReset}
            className="flex-1 h-12 rounded-lg border border-border text-text font-medium hover:bg-gray-50 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            className="flex-1 h-12 rounded-lg bg-accent text-white font-semibold hover:opacity-90 transition-opacity"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}