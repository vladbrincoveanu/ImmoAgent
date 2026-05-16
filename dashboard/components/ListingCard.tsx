'use client';

import React, { useState } from 'react';
import { ListingBase } from '@/lib/types';
import { SOURCE_LABELS, formatPrice } from '@/lib/utils';
import { EquityBadge } from './EquityBadge';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const [imageError, setImageError] = useState(false);

  const hasImage = listing.image_url && !imageError;

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="group bg-white dark:bg-[--color-card] rounded-xl shadow-sm border border-[--color-border] overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="relative aspect-[16/10] bg-[--color-bg] overflow-hidden">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property image'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-[--color-border]">
            <svg className="w-8 h-8 text-[--color-muted]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
            </svg>
          </div>
        )}

        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-[--color-accent]">
              {listing.score}
            </span>
          </div>
        )}

        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-[--color-heading] bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      <div className="p-4">
        <h3 className="font-medium text-[--color-text] line-clamp-2 text-sm leading-snug mb-2">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-[--color-heading] text-base mb-1">
          {formatPrice(listing.price_total, listing.price_is_estimated)}
        </p>
        <div className="mb-1">
          <EquityBadge
            downPct={listing.estimated_down_pct}
            downPctKimv={listing.estimated_down_pct_kimv}
            equityEur={listing.estimated_equity_eur}
            confidence={listing.bank_score_confidence}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[--color-muted]">
            {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
            {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
          </div>
          {listing.bezirk && (
            <span className="text-[10px] font-medium text-[--color-muted] bg-[--color-bg] px-1.5 py-0.5 rounded">
              {listing.bezirk}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}