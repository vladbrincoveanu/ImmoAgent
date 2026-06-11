'use client';

import React, { useEffect, useState } from 'react';
import { ListingDetail as ListingDetailType } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingDetailProps {
  id: string;
  onClose: () => void;
}

interface ZoneStats {
  district: string;
  total_in_district: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  min_price: number | null;
  max_price: number | null;
  avg_area: number | null;
  avg_rooms: number | null;
  this_listing: {
    price: number | null;
    price_per_m2: number | null;
    price_vs_avg_pct: number | null;
    price_per_m2_vs_avg_pct: number | null;
  };
  matching_budget: number;
  avg_ubahn_minutes: number | null;
  avg_school_minutes: number | null;
}

export function ListingDetail({ id, onClose }: ListingDetailProps) {
  const [listing, setListing] = useState<ListingDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [urlValid, setUrlValid] = useState<boolean | null>(null);
  const [imageError, setImageError] = useState(false);
  const [zoneStats, setZoneStats] = useState<ZoneStats | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    setImageError(false);
    setUrlValid(null);
    setZoneStats(null);
    fetch(`/api/listings/${id}`)
      .then((r) => r.json())
      .then((data) => {
        setListing(data);
        setUrlValid(data.url_is_valid ?? null);
      })
      .finally(() => setLoading(false));
    fetch(`/api/listings/${id}/zone-stats`)
      .then((r) => r.json())
      .then(setZoneStats)
      .catch(() => {});
  }, [id]);

  const handleRecheck = async () => {
    setChecking(true);
    try {
      const res = await fetch(`/api/listings/${id}/check`, { method: 'POST' });
      const data = await res.json();
      setUrlValid(data.url_is_valid);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {loading ? (
          <div className="p-8 text-center text-gray-500 relative">
            <button
              onClick={onClose}
              className="absolute top-3 right-4 text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              &times;
            </button>
            Loading...
          </div>
        ) : listing ? (
          <>
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <ScoreBadge score={listing.score} />
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              {listing.image_url && !imageError ? (
                <div className="relative w-full h-48 rounded-lg overflow-hidden bg-gray-100">
                  <img
                    src={listing.image_url}
                    alt={listing.title || 'Property image'}
                    className="w-full h-full object-cover"
                    onError={() => setImageError(true)}
                  />
                </div>
              ) : (
                <div className="w-full h-48 rounded-lg bg-gray-100 flex items-center justify-center">
                  <span className="text-gray-400 text-sm">No image available</span>
                </div>
              )}

              <h2 className="text-xl font-bold text-gray-900">{listing.title || listing.address || 'Untitled Property'}</h2>

              <div className="grid grid-cols-2 gap-4 text-sm">
                {listing.price_total && (
                  <div><span className="font-medium">Price:</span> €{listing.price_total.toLocaleString('de-AT')}</div>
                )}
                {listing.area_m2 && <div><span className="font-medium">Area:</span> {listing.area_m2} m²</div>}
                {listing.rooms && <div><span className="font-medium">Rooms:</span> {listing.rooms}</div>}
                {listing.bezirk && <div><span className="font-medium">District:</span> {listing.bezirk}</div>}
                {listing.year_built && <div><span className="font-medium">Year Built:</span> {listing.year_built}</div>}
                {listing.floor && <div><span className="font-medium">Floor:</span> {listing.floor}</div>}
                {listing.condition && <div><span className="font-medium">Condition:</span> {listing.condition}</div>}
                {listing.heating && <div><span className="font-medium">Heating:</span> {listing.heating}</div>}
                {listing.energy_class && <div><span className="font-medium">Energy Class:</span> {listing.energy_class}</div>}
                {listing.hwb_value && <div><span className="font-medium">HWB:</span> {listing.hwb_value}</div>}
                {listing.betriebskosten && <div><span className="font-medium">Betriebskosten:</span> €{listing.betriebskosten}</div>}
                {listing.ubahn_walk_minutes != null && <div><span className="font-medium">U-Bahn:</span> {listing.ubahn_walk_minutes} min</div>}
              </div>

              {listing.estimated_down_pct != null && (
                <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <h3 className="font-semibold text-gray-800 mb-3">Financing (estimated)</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="font-medium text-gray-600">Standard (80% LTV):</span>
                      <span className="ml-2 font-semibold">
                        ~{Math.round(listing.estimated_down_pct)}%
                        {listing.estimated_equity_eur != null && (
                          <span className="text-gray-500 font-normal">
                            {' '}(~€{Math.round(listing.estimated_equity_eur / 1000)}k equity)
                          </span>
                        )}
                      </span>
                    </div>
                    {listing.estimated_down_pct_kimv != null && (
                      <div>
                        <span className="font-medium text-gray-600">KIM-V (90% LTV):</span>
                        <span className="ml-2 font-semibold">
                          ~{Math.round(listing.estimated_down_pct_kimv)}%
                        </span>
                      </div>
                    )}
                    {listing.belehnungswert_factor != null && (
                      <div>
                        <span className="font-medium text-gray-600">Belehnungswert est.:</span>
                        <span className="ml-2">~{Math.round(listing.belehnungswert_factor * 100)}% of asking</span>
                      </div>
                    )}
                    {listing.bank_score_confidence && (
                      <div>
                        <span className="font-medium text-gray-600">Confidence:</span>
                        <span className={`ml-2 ${
                          listing.bank_score_confidence === 'high' ? 'text-green-700' :
                          listing.bank_score_confidence === 'medium' ? 'text-yellow-700' :
                          'text-gray-500'
                        }`}>
                          {listing.bank_score_confidence}
                        </span>
                      </div>
                    )}
                    {listing.energy_class && (
                      <div className="col-span-2 text-xs text-gray-500 mt-1">
                        Based on: Energy {listing.energy_class}
                        {listing.hwb_value != null ? ` (HWB ${listing.hwb_value})` : ''}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {listing.infrastructure_distances && Object.keys(listing.infrastructure_distances).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-1">Infrastructure</h3>
                  <div className="text-sm text-gray-600">
                    {Object.entries(listing.infrastructure_distances).map(([k, v]) => (
                      <p key={k}>{k}: {String(v)}</p>
                    ))}
                  </div>
                </div>
              )}

              {listing.score_breakdown && Object.keys(listing.score_breakdown).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-1">Score Breakdown</h3>
                  <div className="text-sm text-gray-600">
                    {Object.entries(listing.score_breakdown).map(([k, v]) => (
                      <p key={k}>{k}: {typeof v === 'number' ? (v as any).toFixed(1) : v}</p>
                    ))}
                  </div>
                </div>
              )}

              {zoneStats && zoneStats.total_in_district > 0 && (
                <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                  <h3 className="font-medium text-gray-700 mb-2">
                    Zone Analytics — {zoneStats.district}
                  </h3>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    <div className="text-gray-500">Listings in zone</div>
                    <div className="text-right font-medium text-gray-900">{zoneStats.total_in_district}</div>
                    <div className="text-gray-500">Avg price</div>
                    <div className="text-right font-medium text-gray-900">
                      {zoneStats.avg_price != null ? `€${zoneStats.avg_price.toLocaleString('de-AT')}` : '—'}
                    </div>
                    <div className="text-gray-500">Avg €/m²</div>
                    <div className="text-right font-medium text-gray-900">
                      {zoneStats.avg_price_per_m2 != null ? `€${zoneStats.avg_price_per_m2.toLocaleString('de-AT')}` : '—'}
                    </div>
                    <div className="text-gray-500">Price range</div>
                    <div className="text-right font-medium text-gray-900 text-xs">
                      {zoneStats.min_price != null && zoneStats.max_price != null
                        ? `€${zoneStats.min_price.toLocaleString('de-AT')} – €${zoneStats.max_price.toLocaleString('de-AT')}`
                        : '—'}
                    </div>
                    {zoneStats.this_listing.price_vs_avg_pct != null && (
                      <>
                        <div className="text-gray-500">This listing vs avg</div>
                        <div className={`text-right font-medium ${zoneStats.this_listing.price_vs_avg_pct > 0 ? 'text-red-700' : 'text-green-700'}`}>
                          {zoneStats.this_listing.price_vs_avg_pct > 0 ? '+' : ''}{zoneStats.this_listing.price_vs_avg_pct}%
                        </div>
                      </>
                    )}
                    {zoneStats.this_listing.price_per_m2_vs_avg_pct != null && (
                      <>
                        <div className="text-gray-500">€/m² vs avg</div>
                        <div className={`text-right font-medium ${zoneStats.this_listing.price_per_m2_vs_avg_pct > 0 ? 'text-red-700' : 'text-green-700'}`}>
                          {zoneStats.this_listing.price_per_m2_vs_avg_pct > 0 ? '+' : ''}{zoneStats.this_listing.price_per_m2_vs_avg_pct}%
                        </div>
                      </>
                    )}
                    <div className="text-gray-500 border-t border-blue-200 pt-1 mt-1">Matching ≤ €500k</div>
                    <div className="text-right font-medium text-gray-900 border-t border-blue-200 pt-1 mt-1">
                      {zoneStats.matching_budget}
                    </div>
                    {zoneStats.avg_ubahn_minutes != null && (
                      <>
                        <div className="text-gray-500">Avg U-Bahn walk (zone)</div>
                        <div className="text-right font-medium text-gray-900">{zoneStats.avg_ubahn_minutes} min</div>
                      </>
                    )}
                    {zoneStats.avg_school_minutes != null && (
                      <>
                        <div className="text-gray-500">Avg school walk (zone)</div>
                        <div className="text-right font-medium text-gray-900">{zoneStats.avg_school_minutes} min</div>
                      </>
                    )}
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <a
                  href={listing.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Open Original
                </a>
                <button
                  onClick={handleRecheck}
                  disabled={checking}
                  className="px-4 py-2 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {checking ? 'Checking...' : 'Recheck Availability'}
                </button>
                {urlValid !== null && (
                  <span className={`px-3 py-2 text-sm rounded-lg ${urlValid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {urlValid ? 'Available' : 'Unavailable'}
                  </span>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="p-8 text-center text-gray-500 relative">
            <button
              onClick={onClose}
              className="absolute top-3 right-4 text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              &times;
            </button>
            Listing not found
          </div>
        )}
      </div>
    </div>
  );
}
