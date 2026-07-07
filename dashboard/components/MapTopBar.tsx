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
      className="h-14 bg-card border-b border-line flex items-center gap-4 px-5 relative z-[1200] shadow-[0_1px_0_rgba(22,36,58,0.02),0_2px_12px_rgba(22,36,58,0.04)]"
    >
      <span className="flex items-center gap-2.5">
        <span
          aria-hidden
          className="w-7 h-7 rounded-[9px] bg-gradient-to-br from-accent to-[#173ba8] text-white flex items-center justify-center shadow-[0_2px_6px_rgba(36,86,230,0.35)]"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 11l9-7 9 7" />
            <path d="M6 10v9h12v-9" />
          </svg>
        </span>
        <span data-testid="brand" className="font-display font-semibold text-[17px] tracking-tight text-ink">
          Immo Scouter
        </span>
      </span>
      <span className="hidden lg:inline text-[11px] uppercase tracking-[0.14em] text-ink-3 font-medium border-l border-line pl-4">
        Vienna Property Atlas
      </span>
      <div className="flex-1" />
      {profileSlot}
      <button
        data-testid="filters-btn"
        onClick={onFiltersClick}
        className={`flex items-center gap-1.5 text-[13px] font-medium rounded-full px-4 py-1.5 border transition-all duration-150 ${
          filtersOpen
            ? 'text-white bg-accent border-accent shadow-[0_2px_8px_rgba(36,86,230,0.3)]'
            : 'text-ink bg-card border-line hover:border-[#b9c6d6] hover:shadow-sm'
        }`}
      >
        {FILTER_SVG}
        Filters
        {activeFilterCount > 0 && (
          <span
            data-testid="filter-count-badge"
            className={`text-[11px] font-semibold min-w-[18px] h-[18px] rounded-full inline-flex items-center justify-center ${
              filtersOpen ? 'bg-white text-accent' : 'bg-accent text-white'
            }`}
          >
            {activeFilterCount}
          </span>
        )}
      </button>
      <button
        data-testid="layers-btn"
        onClick={onLayersClick}
        className={`flex items-center gap-1.5 text-[13px] font-medium rounded-full px-4 py-1.5 border transition-all duration-150 ${
          layersOpen
            ? 'text-white bg-accent border-accent shadow-[0_2px_8px_rgba(36,86,230,0.3)]'
            : 'text-ink bg-card border-line hover:border-[#b9c6d6] hover:shadow-sm'
        }`}
      >
        {LAYERS_SVG}
        Layers
      </button>
      {filterPopover}
    </header>
  );
}
