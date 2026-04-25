'use client';

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ListingSidebar } from '@/components/ListingSidebar';
import { ListingDetail } from '@/components/ListingDetail';
import { MapLegend } from '@/components/MapLegend';
import { SortOption } from '@/components/FilterBar';
import { MapListing } from '@/lib/types';

const MapView = dynamic(
  () => import('@/components/MapView').then((m) => m.MapView),
  { ssr: false, loading: () => <MapLoadingState /> }
);

function MapLoadingState() {
  return (
    <div className="h-full w-full flex items-center justify-center bg-gray-100">
      <p className="text-gray-500">Loading map...</p>
    </div>
  );
}

export default function MapPage() {
  const [listings, setListings] = useState<MapListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [minScore, setMinScore] = useState('0');
  const [district, setDistrict] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('score_desc');

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (minScore !== '0') params.set('min_score', minScore);
      if (district) params.set('district', district);
      params.set('sort', sortBy);

      const res = await fetch(`/api/listings/map?${params}`);
      const data = await res.json();
      setListings(data.listings ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district, sortBy]);

  useEffect(() => { fetchListings(); }, [fetchListings]);

  const selectedListing = listings.find((l) => l._id === selectedId) ?? null;

  const handlePinClick = (listing: MapListing) => {
    setSelectedId(listing._id);
  };

  const handleSidebarSelect = (listing: MapListing) => {
    setSelectedId(listing._id);
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-warm-bg">
      {/* Header */}
      <header className="h-14 border-b border-gray-200 bg-white flex items-center px-4 shrink-0">
        <h1 className="text-base font-semibold text-gray-900">Property Map</h1>
        <span className="ml-3 text-xs px-2 py-1 rounded bg-blue-100 text-blue-800">
          {selectedId ? `Selected: ${selectedId.slice(0,8)}...` : 'No selection'}
        </span>
        <nav className="ml-auto flex items-center gap-4 text-sm">
          <a href="/dashboard" className="text-gray-500 hover:text-gray-700">Dashboard</a>
          <a href="/dashboard/map" className="text-blue-600 font-medium">Map</a>
        </nav>
      </header>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        <ListingSidebar
          listings={listings}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          district={district}
          onDistrictChange={setDistrict}
          onRefresh={fetchListings}
          selectedId={selectedId}
          onSelect={handleSidebarSelect}
          sortBy={sortBy}
          onSortChange={setSortBy}
        />

        <div className="flex-1 relative">
          {loading ? (
            <div className="h-full flex items-center justify-center bg-gray-50">
              <p className="text-gray-500">Loading...</p>
            </div>
          ) : listings.length === 0 ? (
            <div className="h-full flex items-center justify-center bg-gray-50">
              <p className="text-gray-400">No listings match your filters.</p>
            </div>
          ) : (
            <>
              <MapView
                listings={listings}
                selectedListing={selectedListing}
                onPinClick={handlePinClick}
              />
              <MapLegend />
            </>
          )}
        </div>
      </div>

      {selectedId && (
        <ListingDetail
          id={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}