'use client';

import React from 'react';
import { ListingBase } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const sourceLabel: Record<string, string> = {
    willhaben: 'WH',
    immo_kurier: 'IK',
    derstandard: 'DS',
    unknown: '?',
  };

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="cursor-pointer bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md hover:border-gray-300 transition-all duration-200"
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-medium text-gray-900 line-clamp-2 flex-1 mr-2">
          {listing.title || 'No title'}
        </h3>
        <ScoreBadge score={listing.score} />
      </div>

      <div className="space-y-1 text-sm text-gray-600">
        {listing.price_total && (
          <p className="font-semibold text-gray-900">
            €{listing.price_total.toLocaleString('de-AT')}
          </p>
        )}
        <p>
          {listing.area_m2 ?? '–'} m² &bull; {listing.rooms ?? '–'} rooms
          {listing.bezirk && ` &bull; District ${listing.bezirk}`}
        </p>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {sourceLabel[listing.source_enum] ?? '?'}
        </span>
        {listing.processed_at && (
          <span className="text-xs text-gray-400">
            {new Date(listing.processed_at * 1000).toLocaleDateString('de-AT')}
          </span>
        )}
      </div>
    </div>
  );
}