'use client';

import React, { useEffect, useState } from 'react';
import { ListingDetail as ListingDetailType } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingDetailProps {
  id: string;
  onClose: () => void;
}

export function ListingDetail({ id, onClose }: ListingDetailProps) {
  const [listing, setListing] = useState<ListingDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [urlValid, setUrlValid] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`/api/listings/${id}`)
      .then((r) => r.json())
      .then((data) => {
        setListing(data);
        setUrlValid(data.url_is_valid ?? null);
      })
      .finally(() => setLoading(false));
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
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
              <h2 className="text-xl font-bold text-gray-900">{listing.title || 'No title'}</h2>

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
                      <p key={k}>{k}: {typeof v === 'number' ? v.toFixed(1) : v}</p>
                    ))}
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
          <div className="p-8 text-center text-gray-500">Listing not found</div>
        )}
      </div>
    </div>
  );
}
