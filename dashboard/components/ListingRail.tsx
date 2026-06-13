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
}

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: 'score_desc', label: 'Score · high to low' },
  { value: 'price_asc', label: 'Price · low to high' },
  { value: 'price_desc', label: 'Price · high to low' },
  { value: 'date_desc', label: 'Date · newest first' },
  { value: 'area_desc', label: 'Area · largest first' },
];

export function ListingRail({ listings, selectedId, onSelect, sortMode, onSortChange }: ListingRailProps) {
  return (
    <aside
      data-testid="listing-rail"
      className="w-[340px] flex-shrink-0 bg-card border-r border-line flex flex-col"
    >
      <div className="px-[18px] py-3.5 flex items-baseline justify-between gap-2">
        <span data-testid="rail-count" className="text-[13px] font-semibold">
          {listings.length} in view
        </span>
        <select
          data-testid="rail-sort"
          value={sortMode}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="text-[12px] text-ink-2 bg-transparent border-0 cursor-pointer"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex-1 overflow-y-auto px-2.5 pb-4">
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
