'use client';

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ListingDetail as ListingDetailType } from '@/lib/types';

interface CommuteAndRentPanelProps {
  listing: ListingDetailType;
}

interface CommuteData {
  recommended: { minutes: number; mode: 'transit' | 'walk' };
  walk: { minutes: number; km: number };
  transit: { minutes: number; route: { from: string; to: string; transfer: string | null } } | null;
}

interface RentData {
  monthly_rent_eur: number;
  annual_rent_eur: number;
  gross_yield_pct: number;
  net_yield_pct: number;
  rent_per_m2: number;
  is_above_market: boolean;
}

function formatK(value: number): string {
  if (value >= 1000) return `€${Math.round(value / 1000)}k`;
  return `€${value}`;
}

export function CommuteAndRentPanel({ listing }: CommuteAndRentPanelProps) {
  const searchParams = useSearchParams();
  const destLat = searchParams.get('dest_lat');
  const destLon = searchParams.get('dest_lon');
  const destName = searchParams.get('dest_name') ?? '';

  const [commute, setCommute] = useState<CommuteData | null>(null);
  const [rent, setRent] = useState<RentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCommute(null);
    setRent(null);

    const lat = (listing as { coordinates?: { lat: number; lon: number } | null }).coordinates?.lat
      ?? null;
    const lon = (listing as { coordinates?: { lat: number; lon: number } | null }).coordinates?.lon
      ?? null;
    const destLatNum = destLat ? Number(destLat) : null;
    const destLonNum = destLon ? Number(destLon) : null;

    const fetches: Array<Promise<void>> = [];

    if (lat != null && lon != null && destLatNum != null && destLonNum != null) {
      fetches.push(
        fetch(`/api/commute?lat=${lat}&lon=${lon}&dest_lat=${destLatNum}&dest_lon=${destLonNum}&dest_name=${encodeURIComponent(destName)}`)
          .then((r) => r.json())
          .then((d) => { if (!cancelled) setCommute(d); })
          .catch(() => {})
      );
    }
    if (listing.area_m2 && listing.price_total) {
      const qs = new URLSearchParams({
        area_m2: String(listing.area_m2),
        price_total: String(listing.price_total),
        ...(listing.bezirk ? { bezirk: listing.bezirk } : {}),
      });
      fetches.push(
        fetch(`/api/rent-estimate?${qs.toString()}`)
          .then((r) => r.json())
          .then((d) => { if (!cancelled) setRent(d); })
          .catch(() => {})
      );
    }

    Promise.all(fetches).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [listing, destLat, destLon, destName]);

  if (loading && !commute && !rent) {
    return (
      <div className="mt-5 pt-4 border-t border-gray-200 text-xs text-muted" data-testid="commute-rent-loading">
        Loading commute &amp; rent estimate…
      </div>
    );
  }

  if (!commute && !rent) return null;

  return (
    <div className="mt-5 pt-4 border-t border-gray-200 grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="commute-rent-section">
      {commute && (
        <div className="rounded-lg border border-gray-200 p-3 bg-white" data-testid="commute-panel">
          <p className="text-[10px] uppercase tracking-wide text-muted font-semibold mb-1">Commute to {destName.split(/[()]/)[0].trim()}</p>
          <p className="text-2xl font-bold text-heading">
            {commute.recommended.minutes}<span className="text-sm font-medium text-muted ml-1">min</span>
          </p>
          <p className="text-xs text-muted mt-0.5">
            {commute.recommended.mode === 'transit' ? 'by U-Bahn' : 'walking'}
            {commute.transit?.route && (
              <> · {commute.transit.route.from} → {commute.transit.route.to}</>
            )}
          </p>
          <div className="grid grid-cols-2 gap-2 mt-2 text-[11px]">
            <div>
              <span className="text-muted">Walk only:</span>
              <span className="ml-1 font-medium">{commute.walk.minutes} min</span>
              <span className="text-muted"> · {commute.walk.km} km</span>
            </div>
            {commute.transit && (
              <div>
                <span className="text-muted">By U-Bahn:</span>
                <span className="ml-1 font-medium">{commute.transit.minutes} min</span>
              </div>
            )}
          </div>
        </div>
      )}
      {rent && (
        <div className="rounded-lg border border-gray-200 p-3 bg-white" data-testid="rent-panel">
          <p className="text-[10px] uppercase tracking-wide text-muted font-semibold mb-1">Estimated rent &amp; yield</p>
          <p className="text-2xl font-bold text-heading">
            {formatK(rent.monthly_rent_eur)}<span className="text-sm font-medium text-muted ml-1">/mo</span>
          </p>
          <p className="text-xs text-muted mt-0.5">
            {rent.gross_yield_pct}% gross · {rent.net_yield_pct}% net yield
          </p>
          <div className="grid grid-cols-2 gap-2 mt-2 text-[11px]">
            <div>
              <span className="text-muted">Annual:</span>
              <span className="ml-1 font-medium">{formatK(rent.annual_rent_eur)}</span>
            </div>
            <div>
              <span className="text-muted">€/m²:</span>
              <span className="ml-1 font-medium">€{rent.rent_per_m2}</span>
            </div>
          </div>
          {rent.is_above_market && (
            <p className="text-[10px] text-red-700 mt-1">⚠ Below-market yield — may sit vacant</p>
          )}
          {rent.gross_yield_pct >= 4.5 && (
            <p className="text-[10px] text-green-700 mt-1">✓ Above-market yield for Vienna</p>
          )}
        </div>
      )}
    </div>
  );
}
