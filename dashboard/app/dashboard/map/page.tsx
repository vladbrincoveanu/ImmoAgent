'use client';

import React, { useState, useCallback, useEffect, useMemo, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import type { ViewportBounds, LayerState, StationFeature, SchoolFeature } from '@/components/MapView';
import { MapTopBar } from '@/components/MapTopBar';
import { MapFilterPopover, type MapFilterState, COMMUTE_COORDS } from '@/components/MapFilterPopover';
import { MapLayersPopover } from '@/components/MapLayersPopover';
import { ListingRail } from '@/components/ListingRail';
import { ListingDetail } from '@/components/ListingDetail';
import { SelectedCard } from '@/components/SelectedCard';
import { BottomSheet } from '@/components/BottomSheet';
import { FilterDrawer } from '@/components/FilterDrawer';
import { CompactListingStrip } from '@/components/CompactListingStrip';
import { ProfileSelector } from '@/components/ProfileSelector';
import { MapListing } from '@/lib/types';
import { useListingsSSE } from '@/lib/sse';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { useFilters } from '@/lib/useFilters';
import { SortOption } from '@/lib/filters';
import { estimateWalkMinutes, haversineKm } from '@/lib/geo';

const MapViewDynamic = dynamic(
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
  const searchParams = useSearchParams();
  const {
    minScore, district, sortBy, maxPrice, showUnfinanceable,
    equity, rate, maxEquity, profile, belowAvgPct,
    destName, destLat, destLon, maxCommute, genossenschaft,
    update,
  } = useFilters();

  const [listings, setListings] = useState<MapListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const [bounds, setBounds] = useState<ViewportBounds | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  // New layout state
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [layers, setLayers] = useState<LayerState>({
    listings: true,
    stations: true,
    schools: true,
    heatmap: false,
  });
  const [stationData, setStationData] = useState<StationFeature[]>([]);
  const [schoolData, setSchoolData] = useState<SchoolFeature[]>([]);
  const [railSort, setRailSort] = useState<SortOption>(sortBy || 'score_desc');
  const [viewportMode, setViewportMode] = useState<'desktop' | 'mobile' | null>(null);

  const { newListings } = useListingsSSE();

  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const updateViewportMode = () => setViewportMode(media.matches ? 'desktop' : 'mobile');
    updateViewportMode();
    media.addEventListener('change', updateViewportMode);
    return () => media.removeEventListener('change', updateViewportMode);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/geo/infrastructure')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !Array.isArray(data?.features)) return;
        const feats = data.features as Array<StationFeature | SchoolFeature>;
        setStationData(feats.filter((f): f is StationFeature => f.properties.kind === 'ubahn'));
        setSchoolData(feats.filter((f): f is SchoolFeature => f.properties.kind === 'school'));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

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
          coordinate_source: 'none',
          price_is_estimated: false,
          landmark_hint: null,
        }));
      if (merged.length === 0) return prev;
      return [...merged, ...prev];
    });
  }, [newListings]);

  const fetchListings = useCallback(async (signal?: AbortSignal) => {
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
      if (genossenschaft) params.set('genossenschaft', 'true');

      const url = `/api/listings/map?${params.toString()}`;
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`Listings request failed: ${res.status}`);
      const data = await res.json();
      const items = (data.listings ?? []) as Array<MapListing & { scores?: Record<string, number | null> | null }>;
      setListings(items);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      console.error(err);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [minScore, district, sortBy, profile, maxPrice, maxEquity, equity, rate, showUnfinanceable, belowAvgPct, genossenschaft]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchListings(controller.signal);
    return () => controller.abort();
  }, [fetchListings]);

  const filteredListings = useMemo(() => {
    const maxPriceNum = maxPrice ? Number(maxPrice) : null;
    const maxEquityNum = maxEquity ? Number(maxEquity) : null;
    const maxCommuteNum = maxCommute ? Number(maxCommute) : null;
    const destLatNum = destLat ? Number(destLat) : null;
    const destLonNum = destLon ? Number(destLon) : null;
    return listings.filter((l) => {
      if (maxPriceNum != null && Number.isFinite(maxPriceNum) && l.price_total != null && l.price_total > maxPriceNum) return false;
      if (maxEquityNum != null && Number.isFinite(maxEquityNum) && l.estimated_equity_eur != null && l.estimated_equity_eur > maxEquityNum) return false;
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
      if (maxCommuteNum != null && Number.isFinite(maxCommuteNum) && destLatNum != null && destLonNum != null) {
        if (l.coordinates) {
          const km = haversineKm(l.coordinates, { lat: destLatNum, lon: destLonNum });
          const walkMin = estimateWalkMinutes(km);
          if (walkMin > maxCommuteNum) return false;
        }
      }
      return true;
    });
  }, [listings, maxPrice, maxEquity, showUnfinanceable, belowAvgPct, maxCommute, destLat, destLon]);

  const viewportListings = useMemo(() => {
    if (!bounds) return filteredListings;
    return filteredListings.filter((l) => {
      if (!l.coordinates) return false;
      const { lat, lon } = l.coordinates;
      return lat >= bounds.south && lat <= bounds.north && lon >= bounds.west && lon <= bounds.east;
    });
  }, [filteredListings, bounds]);

  const noCoordCount = useMemo(
    () => filteredListings.filter((l) => !l.coordinates).length,
    [filteredListings]
  );

  // Apply rail sort to viewport listings
  const sortedRailListings = useMemo(() => {
    const arr = [...viewportListings];
    arr.sort((a, b) => {
      switch (railSort) {
        case 'price_asc':
          return (a.price_total ?? Infinity) - (b.price_total ?? Infinity);
        case 'price_desc':
          return (b.price_total ?? -1) - (a.price_total ?? -1);
        case 'area_desc':
          return (b.area_m2 ?? -1) - (a.area_m2 ?? -1);
        case 'date_desc':
          return 0; // no date on MapListing; preserve insertion order
        case 'score_desc':
        default:
          return (b.score ?? -1) - (a.score ?? -1);
      }
    });
    return arr;
  }, [viewportListings, railSort]);

  const selectedListing = useMemo(
    () => listings.find((l) => l._id === selectedListingId) ?? null,
    [listings, selectedListingId]
  );

  // MapFilterState translation: useFilters (URL) state ↔ MapFilterPopover local state
  const mapFilterState: MapFilterState = useMemo(() => ({
    district,
    minScore: Number(minScore) || 0,
    maxPrice: Number(maxPrice) || 0,
    commuteTo: destName,
    maxCommute: Number(maxCommute) || 45,
  }), [district, minScore, maxPrice, destName, maxCommute]);

  const applyMapFilters = useCallback((next: MapFilterState) => {
    const coords = COMMUTE_COORDS[next.commuteTo] ?? null;
    update({
      district: next.district,
      minScore: String(next.minScore),
      maxPrice: String(next.maxPrice),
      destName: next.commuteTo,
      destLat: coords?.lat ?? '',
      destLon: coords?.lon ?? '',
      maxCommute: next.commuteTo ? String(next.maxCommute) : '',
    });
  }, [update]);

  // Active filter count for top-bar badge
  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (minScore && minScore !== '0') n += 1;
    if (district) n += 1;
    if (maxPrice && maxPrice !== '500000') n += 1;
    if (destName) n += 1;
    if (showUnfinanceable) n += 1;
    if (belowAvgPct) n += 1;
    if (profile !== DEFAULT_PROFILE) n += 1;
    if (genossenschaft) n += 1;
    return n;
  }, [minScore, district, maxPrice, destName, showUnfinanceable, belowAvgPct, profile, genossenschaft]);

  // Layer counts
  const layerCounts = useMemo(() => ({
    listings: listings.length,
    stations: stationData.length,
    schools: schoolData.length,
    heatmap: 23,
  }), [listings, stationData, schoolData]);

  const handlePinClick = useCallback((listing: MapListing) => {
    setSelectedListingId(listing._id);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setDetailId(null);
    setSelectedListingId(null);
  }, []);

  const handleViewDetails = useCallback((id: string) => {
    setDetailId(id);
    setSelectedListingId(null);
  }, []);

  return (
    <>
      {/* DESKTOP — top bar + rail + map */}
      <div className="hidden md:flex flex-col h-screen map-desktop bg-bg">
        <MapTopBar
          activeFilterCount={activeFilterCount}
          filtersOpen={filtersOpen}
          onFiltersClick={() => {
            setFiltersOpen((o) => !o);
            setLayersOpen(false);
          }}
          layersOpen={layersOpen}
          onLayersClick={() => {
            setLayersOpen((o) => !o);
            setFiltersOpen(false);
          }}
          genossenschaftOnly={genossenschaft}
          onGenossenschaftClick={() => update({ genossenschaft: !genossenschaft })}
          profileSlot={
            <ProfileSelector
              value={profile}
              onChange={(v) => {
                if (isValidProfile(v)) update({ profile: v });
              }}
            />
          }
          filterPopover={
            <MapFilterPopover
              open={filtersOpen}
              onClose={() => setFiltersOpen(false)}
              initial={mapFilterState}
              onApply={applyMapFilters}
            />
          }
        />

        <div className="flex flex-1 overflow-hidden">
          <ListingRail
            listings={sortedRailListings}
            selectedId={selectedListingId}
            onSelect={setSelectedListingId}
            sortMode={railSort}
            onSortChange={setRailSort}
            noCoordCount={noCoordCount}
          />

          <div className="flex-1 relative">
            {loading && listings.length === 0 ? (
              <div className="h-full flex items-center justify-center bg-gray-50">
                <p className="text-gray-500">Loading...</p>
              </div>
            ) : listings.length === 0 ? (
              <div className="h-full flex items-center justify-center bg-gray-50">
                <p className="text-gray-400">No listings match your filters.</p>
              </div>
            ) : (
              <>
                {viewportMode === 'desktop' && (
                  <MapViewDynamic
                    listings={viewportListings}
                    selectedListingId={selectedListingId}
                    layers={layers}
                    stationData={stationData}
                    schoolData={schoolData}
                    layersPopoverSlot={
                      <MapLayersPopover
                        open={layersOpen}
                        onClose={() => setLayersOpen(false)}
                        layers={layers}
                        onToggle={(k) => setLayers((s) => ({ ...s, [k]: !s[k] }))}
                        counts={layerCounts}
                      />
                    }
                    onPinClick={handlePinClick}
                    onMapClick={() => setSelectedListingId(null)}
                    onBoundsChange={setBounds}
                  />
                )}
              </>
            )}

            {selectedListing && viewportMode === 'desktop' && (
              <div data-testid="selected-card-slot" className="absolute inset-0 pointer-events-none">
                <div className="pointer-events-auto">
                  <SelectedCard
                    listing={selectedListing}
                    onClose={handleCloseDetail}
                    onViewDetails={handleViewDetails}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* MOBILE — existing BottomSheet flow */}
      <div data-testid="mobile-map-fallback" className="md:hidden">
        <div className="h-[calc(100dvh-48px)] max-h-[calc(100dvh-48px)] flex flex-col overflow-hidden bg-warm-bg">
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
              <ProfileSelector value={profile} onChange={(v) => update({ profile: v })} />
            </div>
          </header>

          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="flex-1 min-h-0 flex overflow-hidden">
              <div className="flex-1 relative">
                {loading && listings.length === 0 ? (
                  <div className="h-full flex items-center justify-center bg-gray-50">
                    <p className="text-gray-500">Loading...</p>
                  </div>
                ) : listings.length === 0 ? (
                  <div className="h-full flex items-center justify-center bg-gray-50">
                    <p className="text-gray-400">No listings match your filters.</p>
                  </div>
                ) : viewportMode === 'mobile' ? (
                    <MapViewDynamic
                      listings={listings}
                      selectedListingId={selectedListingId}
                      layers={layers}
                      stationData={stationData}
                      schoolData={schoolData}
                      onPinClick={handlePinClick}
                      onMapClick={handleCloseDetail}
                      onBoundsChange={setBounds}
                    />
                ) : null}
              </div>
            </div>

            <div className="h-[40vh] min-h-[220px] max-h-[50vh] border-t border-gray-200 bg-white overflow-y-auto shrink-0">
              <CompactListingStrip
                listings={filteredListings}
                hoveredId={null}
                highlightedId={selectedListingId}
                onHover={() => {}}
                onHoverEnd={() => {}}
                onClick={(l) => setSelectedListingId(l._id)}
              />
            </div>
          </div>

          <button
            onClick={() => setFilterDrawerOpen(true)}
            className="md:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-[1100] hover:opacity-90 transition-opacity"
            aria-label="Open filters"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
          </button>

          <FilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            profile={profile}
            onProfileChange={(v) => update({ profile: v })}
            minScore={minScore}
            onMinScoreChange={(v) => update({ minScore: v })}
            district={district}
            onDistrictChange={(v) => update({ district: v })}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={(v) => update({ sortBy: v })}
            maxPrice={maxPrice}
            onMaxPriceChange={(v) => update({ maxPrice: v })}
            showUnfinanceable={showUnfinanceable}
            onShowUnfinanceableChange={(v) => update({ showUnfinanceable: v })}
          />
        </div>
      </div>

      {detailId && (
        <ListingDetail
          id={detailId}
          onClose={handleCloseDetail}
        />
      )}
    </>
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
