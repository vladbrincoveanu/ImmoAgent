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
      className={`relative flex gap-3 pl-3.5 pr-2.5 py-3 rounded-xl cursor-pointer border transition-all duration-150 ${
        selected
          ? 'bg-accent-soft border-[#c9d7fb] shadow-[0_2px_10px_rgba(36,86,230,0.10)]'
          : 'border-transparent hover:bg-bg hover:shadow-[0_1px_6px_rgba(22,36,58,0.06)]'
      }`}
    >
      {selected && (
        <span aria-hidden className="absolute left-1 top-3 bottom-3 w-[3px] rounded-full bg-accent" />
      )}
      <div className="w-[60px] h-[60px] rounded-[10px] flex-shrink-0 bg-gradient-to-br from-[#dde4ee] to-[#c9d3e2] flex items-center justify-center text-ink-3 overflow-hidden ring-1 ring-black/[0.06]">
        {listing.image_url ? (
          <img src={listing.image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          HOUSE_SVG
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div data-testid="price" className="text-[14.5px] font-bold tracking-tight text-ink tabular-nums leading-tight">
          {formatPrice(listing.price_total)}
        </div>
        <div data-testid="title" className="text-[12px] text-ink-2 truncate mt-[3px] mb-[2px] leading-snug">
          {listing.title}
        </div>
        <div data-testid="sub" className="text-[11.5px] text-ink-3 tabular-nums">
          {listing.area_m2?.toFixed(1)} m² · €{pricePerM2}/m²
          {listing.rooms ? ` · ${listing.rooms} Zi` : ''}
        </div>
      </div>
      <span
        data-testid="score"
        className={`self-start text-[11.5px] font-bold px-2 py-0.5 rounded-full tabular-nums ring-1 ring-inset ${
          isLowScore ? 'bg-mid-soft text-mid-ink ring-[#ecd9b8]' : 'bg-good-soft text-good ring-[#c4e5d6]'
        }`}
      >
        {listing.score?.toFixed(1)}
      </span>
    </div>
  );
}
