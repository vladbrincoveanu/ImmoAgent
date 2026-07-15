'use client';

import { MapListing } from '@/lib/types';
import { formatPrice } from '@/lib/utils';

const HOUSE_SVG = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v10h14V10" />
  </svg>
);

interface SlimListingCardProps {
  listing: MapListing;
  selected: boolean;
  onClick: () => void;
}

export function SlimListingCard({ listing, selected, onClick }: SlimListingCardProps) {
  const isLowScore = (listing.score ?? 0) < 28;
  const pricePerM2 =
    listing.area_m2 && listing.area_m2 > 0 && listing.price_total != null
      ? Math.round(listing.price_total / listing.area_m2)
      : null;
  return (
    <div
      data-testid="slim-listing-card"
      data-id={listing._id}
      onClick={onClick}
      className={`flex gap-3 px-2.5 py-3 rounded-[10px] cursor-pointer border ${
        selected ? 'bg-accent-soft border-[#c9d7fb]' : 'border-transparent hover:bg-bg'
      }`}
    >
      <div className="w-14 h-14 rounded-lg flex-shrink-0 bg-gradient-to-br from-[#dde4ee] to-[#c9d3e2] flex items-center justify-center text-ink-3 overflow-hidden">
        {listing.image_url ? (
          <img src={listing.image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          HOUSE_SVG
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div data-testid="price" className="text-[14px] font-bold tracking-tight">
          {formatPrice(listing.price_total)}
        </div>
        <div data-testid="title" className="text-[12.5px] text-ink-2 truncate my-0.5">
          {listing.title}
        </div>
        <div data-testid="sub" className="text-[11.5px] text-ink-3">
          {listing.area_m2?.toFixed(1)} m² · €{pricePerM2}/m²
        </div>
      </div>
      <span
        data-testid="score"
        className={`self-start text-[11.5px] font-bold px-1.5 py-0.5 rounded-md tabular-nums ${
          isLowScore ? 'bg-mid-soft text-mid-ink' : 'bg-good-soft text-good'
        }`}
      >
        {listing.score?.toFixed(1)}
      </span>
    </div>
  );
}
