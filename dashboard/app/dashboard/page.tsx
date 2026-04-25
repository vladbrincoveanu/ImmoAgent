'use client';

import React, { useState, useCallback } from 'react';
import { ListingCard } from '@/components/ListingCard';
import { FilterBar, SortOption } from '@/components/FilterBar';
import { FilterDrawer } from '@/components/FilterDrawer';
import { ListingDetail } from '@/components/ListingDetail';
import { ListingBase } from '@/lib/types';

export default function DashboardPage() {
  const [listings, setListings] = useState<ListingBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [minScore, setMinScore] = useState('0');
  const [district, setDistrict] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('score_desc');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (minScore !== '0') params.set('min_score', minScore);
      if (district) params.set('district', district);
      params.set('sort', sortBy);

      const res = await fetch(`/api/listings/top?${params}`);
      const data = await res.json();
      setListings(data.listings ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district, sortBy]);

  React.useEffect(() => { fetchListings(); }, [fetchListings]);

  return (
    <main className="min-h-screen bg-gray-50 p-6 pb-24 md:pb-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Top Property Picks</h1>
          <p className="text-sm text-gray-500 mt-1">Last 7 days, sorted by score</p>
        </header>

        {/* Desktop-only filter bar */}
        <div className="hidden md:block">
          <FilterBar
            minScore={minScore}
            onMinScoreChange={setMinScore}
            district={district}
            onDistrictChange={setDistrict}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />
        </div>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : listings.length === 0 ? (
          <p className="text-gray-400">No listings found.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {listings.map((l) => (
              <ListingCard key={l._id} listing={l} onClick={setSelectedId} />
            ))}
          </div>
        )}
      </div>

      {/* Mobile filter FAB */}
      <button
        onClick={() => setFilterDrawerOpen(true)}
        className="md:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-50 hover:opacity-90 transition-opacity"
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

      {selectedId && (
        <ListingDetail
          id={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </main>
  );
}