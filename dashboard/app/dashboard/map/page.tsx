'use client';

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ListingSidebar } from '@/components/ListingSidebar';
import { ListingDetail } from '@/components/ListingDetail';
import { MapLegend } from '@/components/MapLegend';
import { SortOption } from '@/components/FilterBar';
import { MapListing } from '@/lib/types';
import { BottomSheet } from '@/components/BottomSheet';
import { FilterDrawer } from '@/components/FilterDrawer';

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
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [snapPoints, setSnapPoints] = useState<[number, number, number]>(() => {
    const h = typeof window !== 'undefined' ? window.innerHeight : 800;
    return [64, Math.round(h * 0.45), Math.round(h * 0.9)];
  });

  useEffect(() => {
    const handleResize = () => {
      const h = window.innerHeight;
      setSnapPoints([64, Math.round(h * 0.45), Math.round(h * 0.9)]);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
      </header>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop sidebar — hidden on mobile */}
        <div className="hidden md:block w-[280px] h-full shrink-0">
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
        </div>

        {/* Mobile bottom sheet */}
        <div className="md:hidden flex-1 relative">
          <BottomSheet
            snapPoints={snapPoints}
            defaultState="half"
            count={listings.length}
          >
            <div className="p-3">
              <div className="text-xs text-gray-500 font-medium mb-2">
                LISTINGS ({listings.length})
              </div>
              <div className="flex flex-col gap-1.5">
                {listings.length === 0 ? (
                  <p className="text-gray-400 text-sm text-center py-4">No listings match your filters.</p>
                ) : (
                  listings.map((l) => (
                    <div
                      key={l._id}
                      onClick={() => handleSidebarSelect(l)}
                      className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
                        selectedId === l._id
                          ? 'border-accent ring-1 ring-accent'
                          : 'border-border hover:border-muted'
                      }`}
                    >
                      <div className="w-16 h-16 rounded-md overflow-hidden bg-border shrink-0 flex items-center justify-center">
                        {l.image_url ? (
                          <img src={l.image_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
                          </svg>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-text line-clamp-1 leading-tight">{l.title || 'Untitled'}</p>
                        <p className="font-bold text-heading mt-0.5">
                          {l.price_total ? `€${l.price_total.toLocaleString('de-AT')}` : '—'}
                        </p>
                        <div className="flex items-center gap-1 mt-0.5">
                          <span className={`px-1 py-0.5 rounded text-[9px] font-medium text-white ${
                            l.coordinate_source === 'exact' ? 'bg-red-500' : l.coordinate_source === 'landmark' ? 'bg-orange-500' : 'bg-muted'
                          }`}>
                            {l.coordinate_source === 'exact' ? 'Pin' : l.coordinate_source === 'landmark' ? '~' : '—'}
                          </span>
                          {l.score && (
                            <span className="px-1 py-0.5 rounded bg-accent text-white text-[9px] font-medium">{l.score}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </BottomSheet>

          {/* Mobile filter FAB */}
          <button
            onClick={() => setFilterDrawerOpen(true)}
            className="md:hidden absolute bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-[1100] hover:opacity-90 transition-opacity"
            aria-label="Open filters"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
          </button>

          {/* Filter drawer modal */}
          <FilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            minScore={minScore}
            onMinScoreChange={setMinScore}
            district={district}
            onDistrictChange={setDistrict}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />
        </div>

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