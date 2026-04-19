// dashboard/components/ListingCard.tsx
'use client';

import React, { useState } from 'react';
import { ListingBase } from '@/lib/types';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  willhaben: 'WH',
  immo_kurier: 'IK',
  derstandard: 'DS',
  unknown: '?',
};

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const [imageError, setImageError] = useState(false);

  const hasImage = listing.image_url && !imageError;

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="group bg-white rounded-xl shadow-sm border border-border overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    >
      {/* Image area */}
      <div className="relative aspect-[16/10] bg-warm-bg overflow-hidden">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property image'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-border">
            <svg className="w-8 h-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
            </svg>
          </div>
        )}

        {/* Score badge — top right */}
        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-accent">
              {listing.score}
            </span>
          </div>
        )}

        {/* Source badge — bottom left */}
        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-heading bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      {/* Details area */}
      <div className="p-4">
        <h3 className="font-medium text-text line-clamp-2 text-sm leading-snug mb-2">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-heading text-base mb-1">
          {listing.price_total
            ? `€${listing.price_total.toLocaleString('de-AT')}`
            : 'Price on request'}
        </p>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted">
            {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
            {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
          </div>
          {listing.bezirk && (
            <span className="text-[10px] font-medium text-muted bg-warm-bg px-1.5 py-0.5 rounded">
              {listing.bezirk}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}