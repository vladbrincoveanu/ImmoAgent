'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ListingCard } from '@/components/ListingCard';
import { FilterBar, SortOption } from '@/components/FilterBar';
import { FilterDrawer } from '@/components/FilterDrawer';
import { ListingDetail } from '@/components/ListingDetail';
import { ListingBase } from '@/lib/types';
import { filtersFromParams, paramsFromFilters } from '@/lib/filters';

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [listings, setListings] = useState<ListingBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const [minScore, setMinScore] = useState<string>('0');
  const [district, setDistrict] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortOption>('score_desc');
  const [maxPrice, setMaxPrice] = useState<string>('500000');
  const [showUnfinanceable, setShowUnfinanceable] = useState<boolean>(false);

  useEffect(() => {
    const filters = filtersFromParams(searchParams);
    setMinScore(filters.minScore);
    setDistrict(filters.district);
    setSortBy(filters.sortBy as SortOption);
    setMaxPrice(filters.maxPrice);
    setShowUnfinanceable(filters.showUnfinanceable);
  }, [searchParams]);

  const pushFilters = useCallback((filters: { minScore: string; district: string; sortBy: string; maxPrice: string; showUnfinanceable: boolean }) => {
    const params = paramsFromFilters(filters);
    router.push(`/dashboard?${params.toString()}`);
  }, [router]);

  const handleMinScoreChange = (v: string) => {
    setMinScore(v);
    pushFilters({ minScore: v, district, sortBy, maxPrice, showUnfinanceable });
  };

  const handleDistrictChange = (v: string) => {
    setDistrict(v);
    pushFilters({ minScore, district: v, sortBy, maxPrice, showUnfinanceable });
  };

  const handleSortChange = (v: SortOption) => {
    setSortBy(v);
    pushFilters({ minScore, district, sortBy: v, maxPrice, showUnfinanceable });
  };

  const handleMaxPriceChange = (v: string) => {
    setMaxPrice(v);
    pushFilters({ minScore, district, sortBy, maxPrice: v, showUnfinanceable });
  };

  const handleShowUnfinanceableChange = (v: boolean) => {
    setShowUnfinanceable(v);
    pushFilters({ minScore, district, sortBy, maxPrice, showUnfinanceable: v });
  };

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

  useEffect(() => { fetchListings(); }, [fetchListings]);

  const filteredListings = useMemo(() => {
    const maxPriceNum = maxPrice ? Number(maxPrice) : null;
    return listings.filter((l) => {
      if (maxPriceNum != null && Number.isFinite(maxPriceNum) && l.price_total != null && l.price_total > maxPriceNum) return false;
      if (
        !showUnfinanceable &&
        l.estimated_down_pct != null &&
        l.estimated_down_pct > 30 &&
        l.bank_score_confidence !== 'low'
      ) return false;
      return true;
    });
  }, [listings, maxPrice, showUnfinanceable]);

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
            onMinScoreChange={handleMinScoreChange}
            district={district}
            onDistrictChange={handleDistrictChange}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={handleSortChange}
            maxPrice={maxPrice}
            onMaxPriceChange={handleMaxPriceChange}
            showUnfinanceable={showUnfinanceable}
            onShowUnfinanceableChange={handleShowUnfinanceableChange}
          />
        </div>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : filteredListings.length === 0 ? (
          <p className="text-gray-400">{listings.length === 0 ? 'No listings found.' : 'All listings filtered out.'}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredListings.map((l) => (
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
        onMinScoreChange={handleMinScoreChange}
        district={district}
        onDistrictChange={handleDistrictChange}
        onRefresh={fetchListings}
        sortBy={sortBy}
        onSortChange={handleSortChange}
        maxPrice={maxPrice}
        onMaxPriceChange={handleMaxPriceChange}
        showUnfinanceable={showUnfinanceable}
        onShowUnfinanceableChange={handleShowUnfinanceableChange}
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