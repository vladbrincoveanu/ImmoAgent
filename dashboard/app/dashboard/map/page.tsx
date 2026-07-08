'use client';

import React, { useState, useCallback, useEffect, useMemo, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { MapView, type ViewportBounds, type LayerState, type StationFeature, type SchoolFeature } from '@/components/MapView';
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
import { PaywallModal } from '@/components/PaywallModal';
import { MapListing } from '@/lib/types';
import { useListingsSSE } from '@/lib/sse';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { useFilters } from '@/lib/useFilters';
import { SortOption } from '@/lib/filters';

const MapViewDynamic = dynamic(
  () => import('@/components/MapView').then((m) => m.MapView),
  { ssr: false, loading: () => <MapLoadingState /> }
);

function MapLoadingState({ label = 'Loading map…' }: { label?: string }) {
  return (
    <div className="h-full w-full flex flex-col items-center justify-center gap-3 bg-bg">
      <span className="w-8 h-8 rounded-full border-2 border-line border-t-accent animate-spin" aria-hidden />
      <p className="text-[13px] text-ink-3 font-medium">{label}</p>
    </div>
  );
}

function MapPage() {
  const searchParams = useSearchParams();
  const {
    minScore, district, sortBy, maxPrice, showUnfinanceable,
    equity, rate, maxEquity, profile, belowAvgPct,
    destName, destLat, destLon, maxCommute,
    update,
  } = useFilters();

  const [listings, setListings] = useState<MapListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const [bounds, setBounds] = useState<ViewportBounds | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [profilePaywall, setProfilePaywall] = useState(false);
  const [snapPoints, setSnapPoints] = useState<[number, number, number]>([64, 360, 720]);
  const [scoresById, setScoresById] = useState<Record<string, Record<string, number | null>>>({});

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

  const { newListings } = useListingsSSE();

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
      if (res.status === 402) {
        // Free tier picked a Pro persona — show paywall, fall back to default
        setProfilePaywall(true);
        update({ profile: DEFAULT_PROFILE });
        return;
      }
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
  }, [minScore, district, sortBy, profile, maxPrice, maxEquity, equity, rate, showUnfinanceable, belowAvgPct, update]);

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

  const filteredListings = useMemo(() => {
    const maxPriceNum = maxPrice ? Number(maxPrice) : null;
    const maxEquityNum = maxEquity ? Number(maxEquity) : null;
    const maxCommuteNum = maxCommute ? Number(maxCommute) : null;
    const destLatNum = destLat ? Number(destLat) : null;
    const destLonNum = destLon ? Number(destLon) : null;
    const WALK_KMH = 4.8;
    function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
      const R = 6371;
      const dLat = (b.lat - a.lat) * Math.PI / 180;
      const dLon = (b.lon - a.lon) * Math.PI / 180;
      const lat1 = a.lat * Math.PI / 180;
      const lat2 = b.lat * Math.PI / 180;
      const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
      return 2 * R * Math.asin(Math.sqrt(x));
    }
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
          const walkMin = Math.round((km / WALK_KMH) * 60);
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
    return n;
  }, [minScore, district, maxPrice, destName, showUnfinanceable, belowAvgPct, profile]);

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
      <PaywallModal open={profilePaywall} reason="pro_profiles" onClose={() => setProfilePaywall(false)} />

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

          <div className="flex-1 relative bg-bg min-w-0">
            <div className="absolute inset-3">
              {loading ? (
                <MapLoadingState label="Loading listings…" />
              ) : listings.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center gap-2 bg-bg">
                  <p className="text-[14px] font-semibold text-ink-2">No listings match your filters</p>
                  <p className="text-[12.5px] text-ink-3">Loosen the score, price or district filters to see more.</p>
                </div>
              ) : (
                <>
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
                </>
              )}
            </div>

            {selectedListing && !loading && (
              <div data-testid="selected-card-slot" className="absolute inset-3 pointer-events-none">
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
                {loading ? (
                  <div className="h-full flex items-center justify-center bg-gray-50">
                    <p className="text-gray-500">Loading...</p>
                  </div>
                ) : listings.length === 0 ? (
                  <div className="h-full flex items-center justify-center bg-gray-50">
                    <p className="text-gray-400">No listings match your filters.</p>
                  </div>
                ) : (
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
                )}
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
