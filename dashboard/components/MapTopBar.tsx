'use client';

import { ReactNode } from 'react';

const FILTER_SVG = (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M2 4h12M4.5 8h7M7 12h2" />
  </svg>
);

const LAYERS_SVG = (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
    <path d="M8 2L14 5 8 8 2 5z" />
    <path d="M2 8.5L8 11.5 14 8.5" opacity="0.55" />
    <path d="M2 11.5L8 14.5 14 11.5" opacity="0.3" />
  </svg>
);

interface MapTopBarProps {
  activeFilterCount: number;
  filtersOpen: boolean;
  onFiltersClick: () => void;
  layersOpen: boolean;
  onLayersClick: () => void;
  profileSlot: ReactNode;
  filterPopover: ReactNode;
}

export function MapTopBar({
  activeFilterCount,
  filtersOpen,
  onFiltersClick,
  layersOpen,
  onLayersClick,
  profileSlot,
  filterPopover,
}: MapTopBarProps) {
  return (
    <header
      data-testid="map-top-bar"
      className="h-14 bg-card border-b border-line flex items-center gap-4 px-5 relative z-[1200]"
    >
      <span data-testid="brand" className="font-bold text-[15px] tracking-tight">
        Immo Scouter
      </span>
      <div className="flex-1" />
      {profileSlot}
      <button
        data-testid="filters-btn"
        onClick={onFiltersClick}
        className="flex items-center gap-1.5 text-[13px] font-medium text-ink bg-card border border-line rounded-lg px-3.5 py-1.5 hover:border-[#cdd6e1]"
      >
        {FILTER_SVG}
        Filters
        {activeFilterCount > 0 && (
          <span
            data-testid="filter-count-badge"
            className="bg-accent text-white text-[11px] font-semibold min-w-[18px] h-[18px] rounded-full inline-flex items-center justify-center"
          >
            {activeFilterCount}
          </span>
        )}
      </button>
      <button
        data-testid="layers-btn"
        onClick={onLayersClick}
        className={`flex items-center gap-1.5 text-[13px] font-medium rounded-lg px-3.5 py-1.5 border ${
          layersOpen
            ? 'text-white bg-accent border-accent'
            : 'text-ink bg-card border-line hover:border-[#cdd6e1]'
        }`}
      >
        {LAYERS_SVG}
        Layers
      </button>
      {filterPopover}
    </header>
  );
}
