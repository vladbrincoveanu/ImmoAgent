'use client';

import React, { useState } from 'react';
import { ListingBase } from '@/lib/types';
import { SOURCE_LABELS, formatPrice } from '@/lib/utils';
import { EquityBadge } from './EquityBadge';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

function formatEur(value: number | null | undefined, suffix = ''): string {
  if (value == null) return '';
  if (value >= 1000) {
    return `EUR ${Math.round(value / 1000)}k${suffix}`;
  }
  return `EUR ${value}${suffix}`;
}

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const [imageError, setImageError] = useState(false);

  const hasImage = listing.image_url && !imageError;

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="group bg-white rounded-xl shadow-sm border border-[#E8E4E0] overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="relative aspect-[16/10] bg-[#F9F7F4] overflow-hidden">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property image'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-[#E8E4E0]">
            <svg className="w-8 h-8 text-[#8B8B8B]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
            </svg>
          </div>
        )}

        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-[#E07A5F]">
              {listing.score}
            </span>
          </div>
        )}

        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-[#3D405B] bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      <div className="p-4">
        <h3 className="font-medium text-[#2D2D2D] line-clamp-2 text-sm leading-snug mb-2">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-[#3D405B] text-base mb-1">
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

        <div className="flex items-center gap-3 text-xs mb-2">
          {listing.monatsrate != null && (
            <span className="text-[#3D405B] font-medium">
              {formatEur(listing.monatsrate, '/mo')}
            </span>
          )}
          {listing.cashNeeded != null && (
            <span className="text-[#3D405B] font-medium">
              {formatEur(listing.cashNeeded)} cash
            </span>
          )}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[#8B8B8B]">
            {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
            {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
          </div>
          {listing.bezirk && (
            <span className="text-[10px] font-medium text-[#8B8B8B] bg-[#F9F7F4] px-1.5 py-0.5 rounded">
              {listing.bezirk}
            </span>
          )}
        </div>
        {listing.coordinate_source && listing.coordinate_source !== 'none' && (
          <div className="mt-1 flex items-center gap-1">
            {listing.coordinate_source === 'exact' && (
              <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-green-700 bg-green-50 px-1.5 py-0.5 rounded" title="Exact address geocoded">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> Exact
              </span>
            )}
            {listing.coordinate_source === 'landmark' && (
              <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-orange-700 bg-orange-50 px-1.5 py-0.5 rounded" title="Geocoded to a nearby landmark">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" /> Landmark
              </span>
            )}
            {listing.coordinate_source === 'district' && (
              <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded" title="District centroid only — address not geocodable">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> District
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
