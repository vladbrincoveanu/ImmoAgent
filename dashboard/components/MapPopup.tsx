'use client';

import React, { useState } from 'react';
import { useMap } from 'react-leaflet';
import { MapListing } from '@/lib/types';
import { SOURCE_LABELS, formatPrice } from '@/lib/utils';

interface MapPopupProps {
  listing: MapListing;
}

export function MapPopup({ listing }: MapPopupProps) {
  const [imageError, setImageError] = useState(false);
  const map = useMap();

  const hasImage = listing.image_url && !imageError;

  return (
    <div className="min-w-[240px] bg-white rounded-lg overflow-hidden font-dm-sans">
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

        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-accent">
              {listing.score}
            </span>
          </div>
        )}

        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-heading bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      <div className="p-3">
        <h3 className="font-medium text-heading line-clamp-2 text-sm leading-snug mb-1">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-heading text-sm mb-1">
          {formatPrice(listing.price_total, listing.price_is_estimated)}
        </p>

        <div className="flex items-center justify-between mb-2">
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

        <button
          onClick={() => map.closePopup()}
          className="text-xs text-blue-600 hover:text-blue-700 cursor-pointer transition-colors duration-150"
        >
          Close
        </button>
      </div>
    </div>
  );
}