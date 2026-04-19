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

      <div className="flex-1 overflow-y-auto px-3 pb-3 flex flex-col gap-1.5">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm">No listings match your filters.</p>
        ) : (
          listings.map((l) => (
            <div
              key={l._id}
              onClick={() => onSelect(l)}
              className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
                selectedId === l._id
                  ? 'border-accent ring-1 ring-accent'
                  : 'border-border hover:border-muted'
              }`}
            >
              {/* Thumbnail */}
              <div className="w-16 h-16 rounded-md overflow-hidden bg-border shrink-0 flex items-center justify-center">
                {l.image_url ? (
                  <img src={l.image_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
                  </svg>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text line-clamp-1 leading-tight">{l.title || 'Untitled'}</p>
                <p className="font-bold text-heading mt-0.5">
                  {l.price_total ? `€${l.price_total.toLocaleString('de-AT')}` : '—'}
                </p>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`px-1 py-0.5 rounded text-[9px] font-medium text-white ${
                    l.coordinate_source === 'exact' ? 'bg-red-500' : l.coordinate_source === 'landmark' ? 'bg-orange-500' : 'bg-muted'
                  }`}>
                    {l.coordinate_source === 'exact' ? 'Pin' : l.coordinate_source === 'landmark' ? '~' : '—'}
                  </span>
                  {l.score && (
                    <span className="px-1 py-0.5 rounded bg-accent text-white text-[9px] font-medium">{l.score}</span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
