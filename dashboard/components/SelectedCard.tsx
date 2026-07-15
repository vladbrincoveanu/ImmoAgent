'use client';

import React from 'react';
import { MapListing } from '@/lib/types';
import { formatPrice } from '@/lib/utils';

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

  return (
    <div
      data-testid="selected-card"
      className="absolute left-3.5 bottom-3.5 w-[320px] bg-card border border-line rounded-xl shadow-[0_16px_40px_rgba(22,36,58,0.16)] p-[18px] z-[1100]"
    >
      <button
        data-testid="selected-close"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-2.5 right-3 border-0 bg-transparent text-[16px] leading-none text-ink-3 cursor-pointer hover:text-ink"
      >
        ×
      </button>
      <div data-testid="price" className="text-[20px] font-bold tracking-tight">
        {formatPrice(listing.price_total, listing.price_is_estimated)}
      </div>
      <div data-testid="title" className="text-[13px] text-ink-2 mt-1 mb-3 leading-snug line-clamp-2">
        {listing.title || 'Untitled'}
      </div>
      <div className="flex gap-2 flex-wrap">
        {listing.area_m2 != null && (
          <span
            data-testid="fact-m2"
            className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1"
          >
            <strong className="text-ink font-semibold">{listing.area_m2.toFixed(1)} m²</strong>
          </span>
        )}
        {pricePerM2 != null && (
          <span
            data-testid="fact-eur-m2"
            className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1"
          >
            <strong className="text-ink font-semibold">€{pricePerM2}</strong>/m²
          </span>
        )}
        {listing.score != null && (
          <span
            data-testid="fact-score"
            className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1"
          >
            Score <strong className="text-ink font-semibold">{listing.score.toFixed(1)}</strong>
          </span>
        )}
      </div>
      <button
        data-testid="view-listing-cta"
        onClick={() => onViewDetails(listing._id)}
        className="w-full mt-3.5 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg hover:bg-[#1d44c4] transition-colors"
      >
        View listing
      </button>
    </div>
  );
}
