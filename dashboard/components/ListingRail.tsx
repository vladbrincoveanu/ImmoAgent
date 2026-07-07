'use client';

import { MapListing } from '@/lib/types';
import { SlimListingCard } from './SlimListingCard';
import { SortOption } from '@/lib/filters';

interface ListingRailProps {
  listings: MapListing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortMode: SortOption;
  onSortChange: (s: SortOption) => void;
  noCoordCount?: number;
}

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: 'score_desc', label: 'Score · high to low' },
  { value: 'price_asc', label: 'Price · low to high' },
  { value: 'price_desc', label: 'Price · high to low' },
  { value: 'date_desc', label: 'Date · newest first' },
  { value: 'area_desc', label: 'Area · largest first' },
];

export function ListingRail({ listings, selectedId, onSelect, sortMode, onSortChange, noCoordCount = 0 }: ListingRailProps) {
  return (
    <aside
      data-testid="listing-rail"
      className="w-[340px] flex-shrink-0 bg-card border-r border-line flex flex-col"
    >
      <div className="px-[18px] pt-4 pb-3 flex items-baseline justify-between gap-2 border-b border-line/70">
        <span className="flex items-baseline gap-2 min-w-0">
          <span data-testid="rail-count" className="text-[13px] font-semibold text-ink whitespace-nowrap">
            {listings.length} in view
          </span>
          {noCoordCount > 0 && (
            <span data-testid="rail-no-coord" className="text-[11px] text-ink-3 truncate">
              {noCoordCount} without map location
            </span>
          )}
        </span>
        <select
          data-testid="rail-sort"
          value={sortMode}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="text-[12px] font-medium text-ink-2 bg-bg border border-line rounded-full pl-3 pr-2 py-1 cursor-pointer hover:border-[#b9c6d6] transition-colors"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="rail-scroll flex-1 overflow-y-auto px-2.5 pt-2 pb-4 space-y-0.5">
        {listings.map((l) => (
          <SlimListingCard
            key={l._id}
            listing={l}
            selected={l._id === selectedId}
            onClick={() => onSelect(l._id)}
          />
        ))}
      </div>
    </aside>
  );
}
