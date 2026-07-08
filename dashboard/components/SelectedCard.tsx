'use client';

import React from 'react';
import { MapListing } from '@/lib/types';
import { formatPrice } from '@/lib/utils';

const HOUSE_SVG = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" className="text-ink-3">
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v10h14V10" />
  </svg>
);

interface SelectedCardProps {
  listing: MapListing | null;
  onClose: () => void;
  onViewDetails: (id: string) => void;
}

export function SelectedCard({ listing, onClose, onViewDetails }: SelectedCardProps) {
  if (listing == null) return null;

  const pricePerM2 =
    listing.price_total != null && listing.area_m2
      ? Math.round(listing.price_total / listing.area_m2)
      : null;
  const isLowScore = (listing.score ?? 0) < 28;

  return (
    <div
      data-testid="selected-card"
      className="absolute left-3.5 bottom-3.5 w-[320px] bg-card border border-line rounded-2xl shadow-[0_8px_32px_rgba(22,36,58,0.18),0_2px_8px_rgba(22,36,58,0.08)] p-3.5 z-[1100]"
    >
      {/* Header row: thumbnail + info */}
      <div className="flex gap-3">
        <div className="w-[68px] h-[68px] rounded-[10px] shrink-0 bg-gradient-to-br from-[#dde4ee] to-[#c9d3e2] flex items-center justify-center overflow-hidden ring-1 ring-black/[0.06]">
          {listing.image_url ? (
            <img src={listing.image_url} alt="" className="w-full h-full object-cover" />
          ) : (
            HOUSE_SVG
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div data-testid="price" className="text-[17px] font-bold tracking-tight text-ink tabular-nums leading-tight">
            {formatPrice(listing.price_total, listing.price_is_estimated)}
          </div>
          <div data-testid="title" className="text-[12px] text-ink-2 mt-0.5 mb-1.5 leading-snug line-clamp-2">
            {listing.title || 'Untitled'}
          </div>
          <div data-testid="sub" className="text-[11.5px] text-ink-3 tabular-nums">
            {listing.area_m2 != null && <span data-testid="fact-m2">{listing.area_m2.toFixed(1)} m²</span>}
            {pricePerM2 != null && <span data-testid="fact-eur-m2"> · €{pricePerM2}/m²</span>}
            {listing.rooms != null && ` · ${listing.rooms} Zi`}
            {listing.ubahn_walk_minutes != null && ` · U-Bahn ${listing.ubahn_walk_minutes} min`}
          </div>
        </div>
      </div>

      {/* Score badge + close — overlaid top-right */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        {listing.score != null && (
          <span
            data-testid="fact-score"
            className={`text-[11.5px] font-bold px-2 py-0.5 rounded-full tabular-nums ring-1 ring-inset ${
              isLowScore
                ? 'bg-mid-soft text-mid-ink ring-[#ecd9b8]'
                : 'bg-good-soft text-good ring-[#c4e5d6]'
            }`}
          >
            {listing.score.toFixed(1)}
          </span>
        )}
        <button
          data-testid="selected-close"
          onClick={onClose}
          aria-label="Close"
          className="w-6 h-6 flex items-center justify-center rounded-full bg-bg text-ink-3 hover:text-ink hover:bg-line transition-colors text-[14px] leading-none cursor-pointer border-0"
        >
          ×
        </button>
      </div>

      <button
        data-testid="view-listing-cta"
        onClick={() => onViewDetails(listing._id)}
        className="w-full mt-3.5 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg hover:bg-[#1d44c4] transition-colors"
      >
        View listing →
      </button>
    </div>
  );
}
