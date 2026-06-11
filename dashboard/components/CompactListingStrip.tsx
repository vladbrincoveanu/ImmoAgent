'use client';

import React from 'react';
import { MapListing } from '@/lib/types';
import { SOURCE_LABELS, formatPrice } from '@/lib/utils';
import { DealScoreBadge } from './DealScoreBadge';
import { ZoneVsAvgBadge } from './ZoneVsAvgBadge';

interface CompactListingStripProps {
  listings: MapListing[];
  hoveredId: string | null;
  highlightedId: string | null;
  onHover: (id: string | null) => void;
  onHoverEnd: () => void;
  onClick: (listing: MapListing) => void;
}

export function CompactListingStrip({ listings, hoveredId, highlightedId, onHover, onHoverEnd, onClick }: CompactListingStripProps) {
  return (
    <div className="p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          {listings.length} listing{listings.length === 1 ? '' : 's'}
        </p>
        <p className="text-[10px] text-gray-400">Click to highlight on map · Click again for details</p>
      </div>
      {listings.length === 0 ? (
        <p className="text-gray-400 text-sm">No listings match your filters.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
          {listings.map((l) => (
            <button
              key={l._id}
              type="button"
              onClick={() => onClick(l)}
              onMouseEnter={() => onHover(l._id)}
              onMouseLeave={onHoverEnd}
              className={`text-left bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs hover:shadow-md ${
                highlightedId === l._id
                  ? 'border-accent ring-2 ring-accent'
                  : hoveredId === l._id
                    ? 'border-blue-400 shadow-sm'
                    : 'border-border'
              }`}
            >
              <div className="flex items-baseline justify-between gap-1 mb-1">
                <span className="font-bold text-heading truncate">
                  {l.price_total ? `€${l.price_total.toLocaleString('de-AT')}` : '—'}
                </span>
                {l.score != null && (
                  <span className="text-[10px] font-bold text-white bg-accent rounded px-1.5 py-0.5 shrink-0">
                    {l.score}
                  </span>
                )}
              </div>
              <p className="text-text line-clamp-1 leading-tight mb-1">{l.title || 'Untitled'}</p>
              <div className="flex items-center gap-1.5 text-[10px] text-muted">
                {l.area_m2 != null && <span>{l.area_m2}m²</span>}
                {l.rooms != null && <span>· {l.rooms} rms</span>}
                {l.bezirk && <span>· {l.bezirk}</span>}
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {l.price_vs_avg_pct != null && (
                  <ZoneVsAvgBadge pct={l.price_vs_avg_pct} />
                )}
                {l.bank_score_confidence && l.estimated_down_pct != null && (
                  <span
                    className={`text-[9px] font-medium rounded px-1.5 py-0.5 ${
                      l.bank_score_confidence === 'high' ? 'bg-green-100 text-green-800' :
                      l.bank_score_confidence === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-gray-100 text-gray-700'
                    }`}
                    title={`Bank score confidence: ${l.bank_score_confidence}`}
                  >
                    {l.bank_score_confidence === 'low' ? '~' : ''}{l.estimated_down_pct}% dp
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
