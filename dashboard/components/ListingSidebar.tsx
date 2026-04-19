'use client';

import React from 'react';
import { FilterBar } from './FilterBar';
import { MapListing } from '@/lib/types';

type SortOption = 'score_desc' | 'price_asc' | 'price_desc' | 'date_desc' | 'area_desc';

interface ListingSidebarProps {
  listings: MapListing[];
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  selectedId: string | null;
  onSelect: (listing: MapListing) => void;
  sortBy?: SortOption;
  onSortChange?: (sort: SortOption) => void;
}

export function ListingSidebar({
  listings,
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh,
  selectedId, onSelect,
  sortBy, onSortChange,
}: ListingSidebarProps) {
  return (
    <div className="w-[280px] h-full flex flex-col border-r border-gray-200 bg-gray-50 overflow-hidden">
      <div className="p-3 border-b border-gray-200 bg-white">
        <FilterBar
          minScore={minScore}
          onMinScoreChange={onMinScoreChange}
          district={district}
          onDistrictChange={onDistrictChange}
          onRefresh={onRefresh}
          sortBy={sortBy}
          onSortChange={onSortChange}
        />
      </div>

      <div className="px-3 py-2 text-xs text-gray-500 font-medium">
        LISTINGS ({listings.length})
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 flex flex-col gap-2">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm">No listings match your filters.</p>
        ) : (
          listings.map((l) => (
            <div
              key={l._id}
              onClick={() => onSelect(l)}
              className={`bg-white rounded-lg border p-3 cursor-pointer transition-all text-xs ${
                selectedId === l._id
                  ? 'border-blue-500 ring-1 ring-blue-500'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-gray-900 truncate">{l.title || 'Untitled'}</p>
              <p className="text-blue-600 font-bold mt-1">
                {l.price_total ? `€${l.price_total.toLocaleString()}` : 'N/A'}
              </p>
              <p className="text-gray-500 mt-1">
                {l.area_m2}m² · {l.rooms} rooms
              </p>
              <div className="flex items-center gap-1 mt-2">
                <span className={`px-1.5 py-0.5 rounded text-white text-[10px] font-medium ${
                  l.coordinate_source === 'exact' ? 'bg-red-500' : 'bg-orange-500'
                }`}>
                  {l.coordinate_source === 'exact' ? 'Exact' : 'Landmark'}
                </span>
                {l.score && (
                  <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[10px]">
                    {l.score}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
