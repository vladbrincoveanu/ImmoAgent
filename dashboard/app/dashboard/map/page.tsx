'use client';

import React, { useState, useCallback, useEffect, useMemo, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { ListingSidebar } from '@/components/ListingSidebar';
import { ListingDetail } from '@/components/ListingDetail';
import { MapLegend } from '@/components/MapLegend';
import { SortOption } from '@/components/FilterBar';
import { ProfileSelector } from '@/components/ProfileSelector';
import { MapListing } from '@/lib/types';
import { BottomSheet } from '@/components/BottomSheet';
import { FilterDrawer } from '@/components/FilterDrawer';
import { SelectedCard } from '@/components/SelectedCard';
import { CompactListingStrip } from '@/components/CompactListingStrip';
import { useListingsSSE } from '@/lib/sse';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { filtersFromParams, paramsFromFilters } from '@/lib/filters';
import type { ViewportBounds } from '@/components/MapView';

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

function MapPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [listings, setListings] = useState<MapListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [bounds, setBounds] = useState<ViewportBounds | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [snapPoints, setSnapPoints] = useState<[number, number, number]>([64, 360, 720]);
  const [scoresById, setScoresById] = useState<Record<string, Record<string, number | null>>>({});

  const initial = useMemo(() => filtersFromParams(searchParams), [searchParams]);
  const [minScore, setMinScore] = useState(initial.minScore);
  const [district, setDistrict] = useState(initial.district);
  const [sortBy, setSortBy] = useState<SortOption>(initial.sortBy as SortOption);
  const [maxPrice, setMaxPrice] = useState(initial.maxPrice);
  const [showUnfinanceable, setShowUnfinanceable] = useState(initial.showUnfinanceable);
  const [equity, setEquity] = useState(initial.equity);
  const [rate, setRate] = useState(initial.rate);
  const [maxEquity, setMaxEquity] = useState(initial.maxEquity);
  const [profile, setProfile] = useState(initial.profile);
  const [belowAvgPct, setBelowAvgPct] = useState(initial.belowAvgPct);

  // React to external URL changes (browser back/forward, link clicks)
  useEffect(() => {
    const f = filtersFromParams(searchParams);
    setMinScore(f.minScore);
    setDistrict(f.district);
    setSortBy(f.sortBy as SortOption);
    setMaxPrice(f.maxPrice);
    setShowUnfinanceable(f.showUnfinanceable);
    setEquity(f.equity);
    setRate(f.rate);
    setMaxEquity(f.maxEquity);
    setProfile(f.profile);
    setBelowAvgPct(f.belowAvgPct);
  }, [searchParams]);

  const pushFilters = useCallback((next: Partial<ReturnType<typeof filtersFromParams>>) => {
    const merged = { minScore, district, sortBy, maxPrice, showUnfinanceable, equity, rate, maxEquity, profile, belowAvgPct, ...next };
    const params = paramsFromFilters(merged);
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }, [router, pathname, minScore, district, sortBy, maxPrice, showUnfinanceable, equity, rate, maxEquity, profile, belowAvgPct]);

  const { newListings } = useListingsSSE();

  useEffect(() => {
    if (newListings.length === 0) return;
    setListings((prev) => {
      const existingIds = new Set(prev.map((l) => l._id));
      const merged = newListings
        .filter((l) => !existingIds.has(l._id))
        .map((l): MapListing => ({
          _id: l._id,
          title: l.title ?? '',
          url: l.url ?? '',
          source_enum: l.source_enum as MapListing['source_enum'],
          bezirk: l.bezirk ?? '',
          price_total: l.price_total ?? null,
          area_m2: l.area_m2 ?? null,
          rooms: l.rooms ?? null,
          score: l.score ?? null,
          image_url: l.image_url ?? null,
          coordinates: null,
          coordinate_source: 'district',
          price_is_estimated: false,
          landmark_hint: null,
        }));
      if (merged.length === 0) return prev;
      return [...merged, ...prev];
    });
  }, [newListings]);

  useEffect(() => {
    const handleResize = () => {
      const h = window.innerHeight;
      setSnapPoints([64, Math.round(h * 0.45), Math.round(h * 0.9)]);
    };
    handleResize();
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
      if (profile !== DEFAULT_PROFILE) params.set('profile', profile);
      if (maxPrice) params.set('max_price', maxPrice);
      if (maxEquity) params.set('max_equity', maxEquity);
      if (equity) params.set('equity', equity);
      if (rate) params.set('rate', rate);
      if (showUnfinanceable) params.set('unfinanceable', 'true');
      if (belowAvgPct) params.set('below_avg_pct', belowAvgPct);

      const res = await fetch(`/api/listings/map?${params}`);
      const data = await res.json();
      const items = (data.listings ?? []) as Array<MapListing & { scores?: Record<string, number | null> | null }>;
      setListings(items);
      const map: Record<string, Record<string, number | null>> = {};
      for (const l of items) {
        map[l._id] = (l.scores && typeof l.scores === 'object') ? l.scores : { [profile]: l.score ?? null };
      }
      setScoresById(map);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district, sortBy, profile, maxPrice, maxEquity, equity, rate, showUnfinanceable, belowAvgPct]);

  useEffect(() => { fetchListings(); }, [fetchListings]);

  // Re-sort locally on profile change
  useEffect(() => {
    if (Object.keys(scoresById).length === 0) return;
    setListings((prev) => {
      const sorted = [...prev].sort((a, b) => {
        const sa = scoresById[a._id]?.[profile] ?? a.score ?? 0;
        const sb = scoresById[b._id]?.[profile] ?? b.score ?? 0;
        return sb - sa;
      });
      return sorted;
    });
  }, [profile, scoresById]);

  const filteredListings = useMemo(() => listings.filter((l) => {
    if (maxPrice && l.price_total != null && l.price_total > Number(maxPrice)) return false;
    if (
      !showUnfinanceable &&
      l.estimated_down_pct != null &&
      l.estimated_down_pct > 30 &&
      l.bank_score_confidence !== 'low'
    ) return false;
    if (belowAvgPct) {
      const threshold = Number(belowAvgPct);
      if (Number.isFinite(threshold) && l.price_vs_avg_pct != null && l.price_vs_avg_pct > -threshold) return false;
    }
    return true;
  }), [listings, maxPrice, showUnfinanceable, belowAvgPct]);

  const viewportListings = useMemo(() => {
    if (!bounds) return filteredListings;
    return filteredListings.filter((l) => {
      if (!l.coordinates) return false;
      const { lat, lon } = l.coordinates;
      return lat >= bounds.south && lat <= bounds.north && lon >= bounds.west && lon <= bounds.east;
    });
  }, [filteredListings, bounds]);

  const highlightedListing = useMemo(
    () => filteredListings.find((l) => l._id === highlightedId) ?? null,
    [filteredListings, highlightedId]
  );

  const handlePinClick = useCallback((listing: MapListing) => {
    setHighlightedId(listing._id);
  }, []);

  const handleSidebarSelect = useCallback((listing: MapListing) => {
    if (highlightedId === listing._id) {
      setDetailId(listing._id);
    } else {
      setDetailId(null);
      setHighlightedId(listing._id);
    }
  }, [highlightedId]);

  const handleCloseDetail = useCallback(() => {
    setDetailId(null);
    queueMicrotask(() => setHighlightedId(null));
  }, []);

  const handleViewDetails = useCallback((id: string) => {
    setDetailId(id);
    setHighlightedId(null);
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-warm-bg">
      {/* Header — ProfileSelector + nav to /dashboard */}
      <header className="h-14 border-b border-gray-200 bg-white flex items-center px-4 gap-4 shrink-0">
        <a href={`/dashboard${searchParams.toString() ? `?${searchParams.toString()}` : ''}`}
           className="text-sm text-gray-600 hover:text-gray-900 font-medium flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          List
        </a>
        <h1 className="text-base font-semibold text-gray-900">Property Map</h1>
        <div className="ml-auto">
          <ProfileSelector />
        </div>
      </header>

      {/* Body — split: top (map+sidebar) / bottom (listings strip) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 min-h-0 flex overflow-hidden">
          {/* Desktop sidebar — filter controls only, compact */}
          <div className="hidden md:block w-[260px] h-full shrink-0">
            <ListingSidebar
              listings={viewportListings}
              minScore={minScore}
              onMinScoreChange={(v) => { setMinScore(v); pushFilters({ minScore: v }); }}
              district={district}
              onDistrictChange={(v) => { setDistrict(v); pushFilters({ district: v }); }}
              onRefresh={fetchListings}
              selectedId={highlightedId}
              onSelect={handleSidebarSelect}
              sortBy={sortBy}
              onSortChange={(v) => { setSortBy(v); pushFilters({ sortBy: v }); }}
              viewportCount={viewportListings.length}
              hoveredId={hoveredId}
              onHover={setHoveredId}
              onHoverEnd={() => setHoveredId(null)}
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
                  highlightedId={highlightedId}
                  hoveredId={hoveredId}
                  onHover={setHoveredId}
                  onHoverEnd={() => setHoveredId(null)}
                  onBoundsChange={setBounds}
                  onPinClick={(id) => {
                    const found = listings.find((l) => l._id === id);
                    if (found) handlePinClick(found);
                  }}
                  onMapClick={handleCloseDetail}
                />
                <SelectedCard
                  listing={highlightedListing}
                  onClose={handleCloseDetail}
                  onViewDetails={handleViewDetails}
                />
                <MapLegend />
              </>
            )}
          </div>
        </div>

        {/* Bottom strip — listings grid that fits the rest of the viewport */}
        <div className="h-[42vh] min-h-[260px] border-t border-gray-200 bg-white overflow-y-auto shrink-0">
          <CompactListingStrip
            listings={filteredListings}
            hoveredId={hoveredId}
            highlightedId={highlightedId}
            onHover={setHoveredId}
            onHoverEnd={() => setHoveredId(null)}
            onClick={handleSidebarSelect}
          />
        </div>
      </div>

      {/* Mobile filter FAB */}
      <button
        onClick={() => setFilterDrawerOpen(true)}
        className="md:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-[1100] hover:opacity-90 transition-opacity"
        aria-label="Open filters"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
        </svg>
      </button>

      {/* Filter drawer (mobile) */}
      <FilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        minScore={minScore}
        onMinScoreChange={(v) => { setMinScore(v); pushFilters({ minScore: v }); }}
        district={district}
        onDistrictChange={(v) => { setDistrict(v); pushFilters({ district: v }); }}
        onRefresh={fetchListings}
        sortBy={sortBy}
        onSortChange={(v) => { setSortBy(v); pushFilters({ sortBy: v }); }}
        maxPrice={maxPrice}
        onMaxPriceChange={(v) => { setMaxPrice(v); pushFilters({ maxPrice: v }); }}
        showUnfinanceable={showUnfinanceable}
        onShowUnfinanceableChange={(v) => { setShowUnfinanceable(v); pushFilters({ showUnfinanceable: v }); }}
      />

      {detailId && (
        <ListingDetail
          id={detailId}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  );
}

function MapPageWrapper() {
  return (
    <Suspense fallback={<div className="h-screen flex items-center justify-center bg-gray-100"><p className="text-gray-500">Loading map...</p></div>}>
      <MapPage />
    </Suspense>
  );
}

export default MapPageWrapper;
