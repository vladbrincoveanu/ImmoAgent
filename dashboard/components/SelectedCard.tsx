'use client';

import React from 'react';
import { MapListing } from '@/lib/types';
import { EquityBadge } from './EquityBadge';
import { formatPrice, SOURCE_LABELS } from '@/lib/utils';

interface SelectedCardProps {
  listing: MapListing | null;
  onClose: () => void;
  onViewDetails: (id: string) => void;
}

export function SelectedCard({ listing, onClose, onViewDetails }: SelectedCardProps) {
  if (listing == null) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[1000] w-[90vw] max-w-md">
      <div className="bg-white rounded-2xl shadow-2xl border border-border overflow-hidden">
        <div className="relative">
          <div className="relative aspect-[16/9] bg-warm-bg overflow-hidden">
            {listing.image_url ? (
              <img
                src={listing.image_url}
                alt={listing.title || 'Property image'}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-border">
                <svg className="w-10 h-10 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
                </svg>
              </div>
            )}

            <button
              onClick={onClose}
              className="absolute top-2 right-2 w-8 h-8 rounded-full bg-white bg-opacity-90 flex items-center justify-center shadow-md hover:bg-opacity-100 transition-all"
            >
              <svg className="w-4 h-4 text-heading" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {listing.score != null && (
              <div className="absolute top-2 left-2">
                <span className="inline-flex items-center px-2.5 py-1 rounded-md text-sm font-bold text-white bg-accent">
                  {listing.score}
                </span>
              </div>
            )}

            <div className="absolute bottom-2 left-2">
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium text-heading bg-white bg-opacity-90">
                {SOURCE_LABELS[listing.source_enum] ?? '?'}
              </span>
            </div>
          </div>
        </div>

        <div className="p-4">
          <h3 className="font-semibold text-text text-base leading-snug mb-2 line-clamp-2">
            {listing.title || 'Untitled'}
          </h3>

          <div className="flex items-center gap-2 mb-2">
            <p className="font-bold text-heading text-lg">
              {formatPrice(listing.price_total, listing.price_is_estimated)}
            </p>
            {listing.estimated_down_pct != null && (
              <EquityBadge
                downPct={listing.estimated_down_pct}
                equityEur={listing.estimated_equity_eur}
                confidence={listing.bank_score_confidence}
              />
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted">
              {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
              {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
              {listing.bezirk && <span>· {listing.bezirk}</span>}
            </div>

            <button
              onClick={() => onViewDetails(listing._id)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white bg-accent hover:bg-accent-hover transition-colors"
            >
              View details
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}