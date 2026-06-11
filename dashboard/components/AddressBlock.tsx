'use client';

import React from 'react';
import { CoordinateSource, Coordinates } from '@/lib/types';

interface AddressBlockProps {
  address: string | null | undefined;
  bezirk: string | null | undefined;
  coordinateSource: CoordinateSource | undefined;
  coordinates: Coordinates | null | undefined;
  destLat?: number;
  destLon?: number;
  destName?: string;
  variant?: 'card' | 'detail';
}

export function AddressBlock({
  address, bezirk, coordinateSource, coordinates,
  destLat, destLon, destName, variant = 'card',
}: AddressBlockProps) {
  const isExact = coordinateSource === 'exact';
  const isLandmark = coordinateSource === 'landmark';
  const displayAddress = isExact
    ? address
    : (isLandmark ? address : null);

  const mapsHref = coordinates && (destLat != null && destLon != null)
    ? `https://www.google.com/maps/dir/${coordinates.lat},${coordinates.lon}/${destLat},${destLon}/data=!3m1!4b1!4m2!4m1!3e3`
    : (coordinates ? `https://www.google.com/maps/dir/?api=1&destination=${destLat ?? 48.2082},${destLon ?? 16.3738}&origin=${coordinates.lat},${coordinates.lon}&travelmode=transit` : null);

  if (variant === 'card') {
    if (!isExact) return null;
    return (
      <div className="text-[10px] text-emerald-700 font-medium mt-1 flex items-center gap-1" data-testid="address-card">
        <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        <span className="truncate">{displayAddress}</span>
      </div>
    );
  }

  // detail variant
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3" data-testid="address-detail">
      <div className="flex items-start gap-2">
        <svg className="w-4 h-4 text-emerald-700 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 break-words">
            {displayAddress || (isLandmark ? `Approximate: near ${bezirk ? `${bezirk} Wien` : 'this area'}` : bezirk ? `${bezirk} Wien (district centroid)` : 'Location not yet geocoded')}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-muted font-semibold mt-0.5">
            {isExact && <span className="text-emerald-700">✓ Exact address geocoded</span>}
            {isLandmark && <span className="text-orange-700">◉ Landmark vicinity</span>}
            {!isExact && !isLandmark && <span className="text-blue-700">◆ District centroid</span>}
            {coordinates && (
              <span className="text-gray-500 ml-2 font-mono">
                {coordinates.lat.toFixed(4)}, {coordinates.lon.toFixed(4)}
              </span>
            )}
          </p>
        </div>
      </div>
      {mapsHref && (
        <a
          href={mapsHref}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:underline"
          data-testid="directions-link"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-7-7m0 0l7-7m-7 7h18"/></svg>
          Get directions
          {destName ? ` to ${destName}` : ' on Google Maps'}
        </a>
      )}
    </div>
  );
}
