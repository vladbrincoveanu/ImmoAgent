'use client';

import React from 'react';

interface FilterBarProps {
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
}

export function FilterBar({
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <div className="flex items-center gap-2">
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
    </div>
  );
}