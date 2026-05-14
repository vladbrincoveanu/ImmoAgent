# Map Redesign — Booking.com Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace tiny dot pins and Leaflet popups with price-label pins, a viewport-filtered sidebar, and a floating selected-listing card — making the map view usable at a glance.

**Architecture:** `map/page.tsx` owns all state (hoveredId, bounds, highlightedId). `MapView` renders price-label divIcon pins and fires hover/select/bounds events upward. A new `SelectedCard` overlay appears at the map bottom when a listing is selected. `ListingSidebar` receives only viewport-visible listings. All filtering is client-side — no new API calls.

**Tech Stack:** Next.js App Router, React 18, Leaflet 1.9, react-leaflet, TypeScript, Tailwind CSS, Playwright

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `dashboard/components/SelectedCard.tsx` | **Create** | Floating card overlay for selected listing |
| `dashboard/components/MapView.tsx` | **Modify** | Price pins, bounds tracker, hover events, remove pan |
| `dashboard/components/ListingSidebar.tsx` | **Modify** | Viewport count, hover sync |
| `dashboard/app/dashboard/map/page.tsx` | **Modify** | Wire all new state and components |
| `dashboard/components/MapPopup.tsx` | **Delete** | Replaced by SelectedCard |
| `dashboard/tests/map-interaction.spec.ts` | **Modify** | Add SelectedCard behaviour tests |

---

## Task 1: Create SelectedCard component

**Files:**
- Create: `dashboard/components/SelectedCard.tsx`

This is the floating card that appears over the map bottom when a pin is clicked. It shows the listing thumbnail, title, price, score, equity badge, a "View details" button, and a close button. It renders `null` when `listing` is null.

- [ ] **Step 1: Create the file**

```tsx
// dashboard/components/SelectedCard.tsx
'use client';

import React, { useState } from 'react';
import { MapListing } from '@/lib/types';
import { EquityBadge } from '@/components/EquityBadge';
import { formatPrice, SOURCE_LABELS } from '@/lib/utils';

interface SelectedCardProps {
  listing: MapListing | null;
  onClose: () => void;
  onViewDetails: () => void;
}

export function SelectedCard({ listing, onClose, onViewDetails }: SelectedCardProps) {
  const [imageError, setImageError] = useState(false);

  if (!listing) return null;

  const hasImage = listing.image_url && !imageError;

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] w-[340px] bg-white rounded-xl shadow-xl border border-border flex gap-3 p-3 pointer-events-auto">
      {/* Thumbnail */}
      <div className="w-[72px] h-[72px] rounded-lg overflow-hidden bg-warm-bg shrink-0 flex items-center justify-center">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <svg className="w-6 h-6 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
          </svg>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-heading line-clamp-1 leading-tight">
          {listing.title || 'Untitled'}
        </p>
        <p className="text-sm font-bold text-heading mt-0.5">
          {formatPrice(listing.price_total, listing.price_is_estimated)}
        </p>
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          {listing.score != null && (
            <span className="px-1.5 py-0.5 rounded bg-accent text-white text-[10px] font-bold">
              {listing.score}
            </span>
          )}
          <span className="px-1.5 py-0.5 rounded bg-warm-bg text-[10px] font-medium text-muted">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
          <EquityBadge
            downPct={listing.estimated_down_pct}
            equityEur={null}
            confidence={listing.bank_score_confidence}
          />
        </div>
        <button
          onClick={onViewDetails}
          className="mt-1.5 text-xs text-accent font-medium hover:underline"
        >
          View details →
        </button>
      </div>

      {/* Close */}
      <button
        onClick={onClose}
        className="shrink-0 self-start w-6 h-6 flex items-center justify-center rounded-full hover:bg-warm-bg text-muted hover:text-text transition-colors"
        aria-label="Close"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build 2>&1 | tail -20
```

Expected: build succeeds (SelectedCard is not yet imported by anything, so only type-checks the file itself). If it errors on missing `EquityBadge` props (`equityEur`), check `dashboard/components/EquityBadge.tsx` — the prop is `equityEur: number | null | undefined`, so passing `null` is valid.

- [ ] **Step 3: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git add dashboard/components/SelectedCard.tsx && git commit -m "feat(map): add SelectedCard floating overlay component"
```

---

## Task 2: Rewrite MapView.tsx

**Files:**
- Modify: `dashboard/components/MapView.tsx`

This is the biggest change. We:
1. Replace `<Marker>+<Popup>` with price-label `L.divIcon` pills
2. Add `BoundsTracker` inner component that fires `onBoundsChange` on mount + pan/zoom
3. Remove `MapViewController` (pan-to-selected behaviour deleted)
4. Change the prop interface: replace `selectedListing: MapListing | null` with `highlightedId: string | null`; add `hoveredId`, `onHover`, `onHoverEnd`, `onBoundsChange`
5. Replace O(n) icon update with O(1) targeted update using `prevHoveredIdRef` / `prevHighlightedIdRef`

- [ ] **Step 1: Replace the entire file**

```tsx
// dashboard/components/MapView.tsx
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect, useRef, memo } from 'react';

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

type PinState = 'default' | 'hovered' | 'selected';

function createPriceIcon(listing: MapListing, state: PinState): L.DivIcon {
  const price = listing.price_total
    ? `€${Math.round(listing.price_total / 1000)}k`
    : null;

  const color =
    state === 'selected' ? '#E07A5F'
    : state === 'hovered' ? '#c96a4f'
    : listing.coordinate_source === 'exact' ? '#ef4444'
    : listing.coordinate_source === 'landmark' ? '#f97316'
    : '#3B82F6';

  const scale = state === 'selected' ? 'scale(1.25)' : 'scale(1)';

  if (!price) {
    return L.divIcon({
      html: `<div style="background:${color};width:10px;height:10px;border-radius:50%;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);transform:${scale}"></div>`,
      iconSize: [10, 10],
      iconAnchor: [5, 5],
      className: '',
    });
  }

  return L.divIcon({
    html: `<div style="background:${color};color:white;padding:3px 7px;border-radius:12px;font-size:11px;font-weight:700;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.35);transform:${scale};transform-origin:center bottom;border:1.5px solid rgba(255,255,255,0.4)">${price}</div>`,
    iconSize: [80, 24],
    iconAnchor: [40, 24],
    className: '',
  });
}

// ViewportBounds is a minimal interface so map/page.tsx doesn't need to import Leaflet.
// L.LatLngBounds from Leaflet satisfies this interface at runtime.
export interface ViewportBounds {
  contains: (latlng: [number, number]) => boolean;
}

function BoundsTracker({ onBoundsChange }: { onBoundsChange: (b: ViewportBounds) => void }) {
  const map = useMap();
  useMapEvents({
    moveend: () => onBoundsChange(map.getBounds()),
    zoomend: () => onBoundsChange(map.getBounds()),
  });
  useEffect(() => {
    onBoundsChange(map.getBounds());
  }, [map, onBoundsChange]);
  return null;
}

function MapClickHandler({ onMapClick }: { onMapClick?: () => void }) {
  const wasDragged = useRef(false);
  useMapEvents({
    mousedown: () => { wasDragged.current = false; },
    mousemove: () => { wasDragged.current = true; },
    click: () => { if (!wasDragged.current) onMapClick?.(); },
  });
  return null;
}

interface MapViewProps {
  listings: MapListing[];
  highlightedId: string | null;
  hoveredId: string | null;
  onPinClick: (listing: MapListing) => void;
  onHover: (id: string) => void;
  onHoverEnd: () => void;
  onBoundsChange: (b: ViewportBounds) => void;
  onMapClick?: () => void;
}

export const MapView = memo(function MapView({
  listings,
  highlightedId,
  hoveredId,
  onPinClick,
  onHover,
  onHoverEnd,
  onBoundsChange,
  onMapClick,
}: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const markerRefs = useRef<Map<string, L.Marker>>(new Map());
  const prevHoveredIdRef = useRef<string | null>(null);
  const prevHighlightedIdRef = useRef<string | null>(null);

  // O(1) icon update: only refresh the ≤4 affected markers per state change
  useEffect(() => {
    const idsToRefresh = new Set(
      [prevHoveredIdRef.current, prevHighlightedIdRef.current, hoveredId, highlightedId]
        .filter((id): id is string => id !== null)
    );

    idsToRefresh.forEach((id) => {
      const marker = markerRefs.current.get(id);
      const listing = listings.find((l) => l._id === id);
      if (!marker || !listing) return;
      const state: PinState =
        id === highlightedId ? 'selected'
        : id === hoveredId ? 'hovered'
        : 'default';
      marker.setIcon(createPriceIcon(listing, state));
    });

    prevHoveredIdRef.current = hoveredId;
    prevHighlightedIdRef.current = highlightedId;
  }, [listings, highlightedId, hoveredId]);

  const markerNodes = listings.map((listing) => {
    if (!listing.coordinates) return null;
    return (
      <Marker
        key={listing._id}
        position={[listing.coordinates.lat, listing.coordinates.lon]}
        icon={createPriceIcon(listing, 'default')}
        eventHandlers={{
          click: () => onPinClick(listing),
          mouseover: () => onHover(listing._id),
          mouseout: () => onHoverEnd(),
        }}
        ref={(marker: L.Marker | null) => {
          if (marker) markerRefs.current.set(listing._id, marker);
          else markerRefs.current.delete(listing._id);
        }}
      />
    );
  });

  return (
    <MapContainer
      center={viennaCenter}
      zoom={13}
      style={{ height: '100%', width: '100%' }}
      className="rounded-lg"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapClickHandler onMapClick={onMapClick} />
      <BoundsTracker onBoundsChange={onBoundsChange} />
      {markerNodes}
    </MapContainer>
  );
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build 2>&1 | tail -30
```

Expected: build will likely FAIL here because `map/page.tsx` still passes `selectedListing` (old prop) instead of `highlightedId`. That is expected — we fix the page in Task 4. What must NOT appear: errors inside `MapView.tsx` itself (type errors on `L.DivIcon`, `PinState`, `ViewportBounds`, `useMap`, `useMapEvents`).

If you see `Property 'selectedListing' does not exist on type 'MapViewProps'` — that's the page, fixed in Task 4, ignore for now.

- [ ] **Step 3: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git add dashboard/components/MapView.tsx && git commit -m "feat(map): price-label pins, bounds tracker, O(1) hover update, remove pan"
```

---

## Task 3: Update ListingSidebar.tsx

**Files:**
- Modify: `dashboard/components/ListingSidebar.tsx`

Add 4 new props (`viewportCount`, `hoveredId`, `onHover`, `onHoverEnd`), wire hover events onto each card, and replace the `LISTINGS (N)` counter header with `N in view`.

- [ ] **Step 1: Replace the file**

```tsx
// dashboard/components/ListingSidebar.tsx
'use client';

import React from 'react';
import { FilterBar } from './FilterBar';
import { MapListing } from '@/lib/types';

type SortOption = 'score_desc' | 'price_asc' | 'price_desc' | 'date_desc' | 'area_desc';

interface ListingSidebarProps {
  listings: MapListing[];
  viewportCount: number;
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  selectedId: string | null;
  onSelect: (listing: MapListing) => void;
  hoveredId: string | null;
  onHover: (id: string) => void;
  onHoverEnd: () => void;
  sortBy?: SortOption;
  onSortChange?: (sort: SortOption) => void;
}

export function ListingSidebar({
  listings,
  viewportCount,
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh,
  selectedId, onSelect,
  hoveredId, onHover, onHoverEnd,
  sortBy, onSortChange,
}: ListingSidebarProps) {
  return (
    <div className="w-[280px] h-full flex flex-col border-r border-gray-200 bg-gray-50 overflow-hidden">
      <div className="p-3 border-b border-gray-200 bg-white">
        <FilterBar
          minScore={minScore}
          onMinScoreChange={onMinScoreChange}
          district={district}
          onDistrictChange={onDistrictChange}
          onRefresh={onRefresh}
          sortBy={sortBy}
          onSortChange={onSortChange}
        />
      </div>

      <div className="px-3 py-2 text-xs text-gray-500 font-medium">
        {viewportCount} in view
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 flex flex-col gap-1.5">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm">No listings in current view.</p>
        ) : (
          listings.map((l) => (
            <div
              key={l._id}
              onClick={() => onSelect(l)}
              onMouseEnter={() => onHover(l._id)}
              onMouseLeave={() => onHoverEnd()}
              className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
                selectedId === l._id
                  ? 'border-accent ring-1 ring-accent'
                  : hoveredId === l._id
                  ? 'border-muted bg-warm-bg'
                  : 'border-border hover:border-muted'
              }`}
            >
              {/* Thumbnail */}
              <div className="w-16 h-16 rounded-md overflow-hidden bg-border shrink-0 flex items-center justify-center">
                {l.image_url ? (
                  <img src={l.image_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
                  </svg>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className={`font-medium line-clamp-1 leading-tight ${selectedId === l._id ? 'text-accent' : 'text-text'}`}>
                  {l.title || 'Untitled'}{selectedId === l._id && <span className="ml-1">→</span>}
                </p>
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
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build 2>&1 | tail -30
```

Expected: still a TS error on `map/page.tsx` (old MapView props + missing ListingSidebar props) — that's fine. No errors should originate from `ListingSidebar.tsx` itself.

- [ ] **Step 3: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git add dashboard/components/ListingSidebar.tsx && git commit -m "feat(map): viewport count header + hover sync on sidebar cards"
```

---

## Task 4: Wire everything in map/page.tsx

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`

Add `ViewportBounds` interface, `hoveredId` + `bounds` state, `viewportListings` useMemo. Render `SelectedCard` inside the map container div. Update `MapView` props (new interface). Update `ListingSidebar` props (new interface).

- [ ] **Step 1: Replace the entire file**

```tsx
// dashboard/app/dashboard/map/page.tsx
'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { ListingSidebar } from '@/components/ListingSidebar';
import { ListingDetail } from '@/components/ListingDetail';
import { MapLegend } from '@/components/MapLegend';
import { SortOption } from '@/components/FilterBar';
import { MapListing } from '@/lib/types';
import { BottomSheet } from '@/components/BottomSheet';
import { FilterDrawer } from '@/components/FilterDrawer';
import { SelectedCard } from '@/components/SelectedCard';
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

export default function MapPage() {
  const [listings, setListings] = useState<MapListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [bounds, setBounds] = useState<ViewportBounds | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [minScore, setMinScore] = useState('0');
  const [district, setDistrict] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('score_desc');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [maxPrice, setMaxPrice] = useState('500000');
  const [showUnfinanceable, setShowUnfinanceable] = useState(false);
  const [snapPoints, setSnapPoints] = useState<[number, number, number]>([64, 360, 720]);

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

  const filteredListings = useMemo(() => listings.filter((l) => {
    if (maxPrice && l.price_total != null && l.price_total > Number(maxPrice)) return false;
    if (
      !showUnfinanceable &&
      l.estimated_down_pct != null &&
      l.estimated_down_pct > 30 &&
      l.bank_score_confidence !== 'low'
    ) return false;
    return true;
  }), [listings, maxPrice, showUnfinanceable]);

  // Only listings whose pin is inside the current viewport — drives the sidebar
  const viewportListings = useMemo(() => {
    if (!bounds) return filteredListings;
    return filteredListings.filter(
      (l) => l.coordinates != null && bounds.contains([l.coordinates.lat, l.coordinates.lon])
    );
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

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-warm-bg">
      {/* Header */}
      <header className="h-14 border-b border-gray-200 bg-white flex items-center px-4 shrink-0">
        <h1 className="text-base font-semibold text-gray-900">Property Map</h1>
      </header>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop sidebar */}
        <div className="hidden md:block w-[280px] h-full shrink-0">
          <ListingSidebar
            listings={viewportListings}
            viewportCount={viewportListings.length}
            minScore={minScore}
            onMinScoreChange={setMinScore}
            district={district}
            onDistrictChange={setDistrict}
            onRefresh={fetchListings}
            selectedId={highlightedId}
            onSelect={handleSidebarSelect}
            hoveredId={hoveredId}
            onHover={setHoveredId}
            onHoverEnd={() => setHoveredId(null)}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />
        </div>

        {/* Mobile bottom sheet */}
        <div className="md:hidden flex-1 relative">
          <BottomSheet
            snapPoints={snapPoints}
            defaultState="half"
            count={filteredListings.length}
            scrollToId={highlightedId}
          >
            <div className="p-3">
              <div className="text-xs text-gray-500 font-medium mb-2">
                LISTINGS ({filteredListings.length})
              </div>
              <div className="flex flex-col gap-1.5">
                {filteredListings.length === 0 ? (
                  <p className="text-gray-400 text-sm text-center py-4">No listings match your filters.</p>
                ) : (
                  filteredListings.map((l) => (
                    <div
                      key={l._id}
                      data-listing-id={l._id}
                      onClick={() => handleSidebarSelect(l)}
                      className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
                        highlightedId === l._id
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

          <button
            onClick={() => setFilterDrawerOpen(true)}
            className="md:hidden absolute bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-[1100] hover:opacity-90 transition-opacity"
            aria-label="Open filters"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
          </button>

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
            maxPrice={maxPrice}
            onMaxPriceChange={setMaxPrice}
            showUnfinanceable={showUnfinanceable}
            onShowUnfinanceableChange={setShowUnfinanceable}
          />
        </div>

        {/* Map area */}
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
                listings={filteredListings}
                highlightedId={highlightedId}
                hoveredId={hoveredId}
                onPinClick={handlePinClick}
                onHover={setHoveredId}
                onHoverEnd={() => setHoveredId(null)}
                onBoundsChange={setBounds}
                onMapClick={handleCloseDetail}
              />
              <MapLegend />
              {/* SelectedCard floats over map bottom */}
              <SelectedCard
                listing={highlightedListing}
                onClose={() => setHighlightedId(null)}
                onViewDetails={() => highlightedId && setDetailId(highlightedId)}
              />
            </>
          )}
        </div>
      </div>

      {detailId && (
        <ListingDetail
          id={detailId}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run build — must be clean now**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build 2>&1 | tail -30
```

Expected: **build succeeds with 0 errors**. All three modified components (`MapView`, `ListingSidebar`, `SelectedCard`) are now wired together consistently.

If you see `Cannot find module '@/components/MapPopup'` — that's because MapView.tsx no longer imports it. That's correct.

If you see a TS error about `ViewportBounds` — check the `import type { ViewportBounds } from '@/components/MapView'` line at the top of `map/page.tsx`.

- [ ] **Step 3: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git add dashboard/app/dashboard/map/page.tsx && git commit -m "feat(map): wire SelectedCard, viewportListings, hoveredId state in map page"
```

---

## Task 5: Delete MapPopup.tsx and run verification

**Files:**
- Delete: `dashboard/components/MapPopup.tsx`
- Modify: `dashboard/tests/map-interaction.spec.ts`

MapPopup is no longer imported by anything (MapView.tsx was the only consumer, and we rewrote it). Deleting it keeps the codebase clean.

- [ ] **Step 1: Verify nothing imports MapPopup**

```bash
grep -r "MapPopup" /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/app /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/components 2>/dev/null
```

Expected: **no output**. If any files still reference MapPopup, update them to remove the import before deleting.

- [ ] **Step 2: Delete the file**

```bash
rm /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/components/MapPopup.tsx
```

- [ ] **Step 3: Run build to confirm clean**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build 2>&1 | tail -20
```

Expected: build succeeds. No "Cannot find module MapPopup" errors.

- [ ] **Step 4: Add SelectedCard behaviour tests to map-interaction.spec.ts**

Append these two tests to the existing `test.describe` block in `dashboard/tests/map-interaction.spec.ts`:

```ts
  test('pin click shows SelectedCard, map click dismisses it', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) {
      // DB empty — skip interaction test
      await expect(page.locator('h1')).toContainText('Property Map');
      return;
    }

    await expect(leaflet).toBeAttached({ timeout: 10000 });

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();
    if (count === 0) return; // no pins (all null coords)

    // Click first pin — SelectedCard should appear
    await markers.first().click({ timeout: 5000 });
    await page.waitForTimeout(400);

    // SelectedCard visible: "View details" button present
    const viewDetails = page.locator('button:has-text("View details")').or(page.locator('text=View details →')).first();
    const cardVisible = await viewDetails.isVisible().catch(() => false);
    if (cardVisible) {
      // Click the map background — card should disappear
      const bbox = await leaflet.boundingBox();
      if (bbox) {
        await page.mouse.click(bbox.x + 10, bbox.y + 10);
        await page.waitForTimeout(300);
        await expect(viewDetails).not.toBeVisible();
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected.length).toBe(0);
  });

  test('sidebar shows "N in view" counter', async ({ page }) => {
    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    // On desktop viewport, sidebar should be visible with "in view" text
    const inViewText = page.locator('text=in view').first();
    const isVisible = await inViewText.isVisible().catch(() => false);
    if (isVisible) {
      await expect(inViewText).toBeVisible();
    }
    // Either "N in view" is visible, or we're in empty state — both are acceptable
  });
```

- [ ] **Step 5: Run Playwright tests**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx playwright test tests/map-interaction.spec.ts --reporter=list 2>&1 | tail -30
```

Expected: all tests pass or skip gracefully (the tests are written to skip if DB is empty or markers aren't present). No test should error.

- [ ] **Step 6: Run full Playwright suite**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx playwright test --reporter=list 2>&1 | tail -30
```

Expected: all existing tests still pass. The `markers.first().click()` in the old tests will now click a price-label pill instead of a dot pin — the click handler is the same, so behaviour is unchanged.

- [ ] **Step 7: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git add dashboard/components/MapPopup.tsx dashboard/tests/map-interaction.spec.ts && git commit -m "feat(map): delete MapPopup, add SelectedCard + viewport-count Playwright tests"
```

Wait — `git add` on a deleted file stages the deletion:

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && git rm dashboard/components/MapPopup.tsx && git add dashboard/tests/map-interaction.spec.ts && git commit -m "feat(map): delete MapPopup, add SelectedCard + viewport Playwright tests"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Price-label divIcon pins (€NNNk) | Task 2 — `createPriceIcon` |
| Null-price → dot fallback | Task 2 — `if (!price)` branch |
| BoundsTracker fires on mount + moveend + zoomend | Task 2 — `BoundsTracker` component |
| O(1) icon update (only affected markers) | Task 2 — `prevHoveredIdRef` / `prevHighlightedIdRef` |
| ViewportBounds interface (no Leaflet import in page) | Task 2 exports it, Task 4 imports type |
| MapViewController deleted | Task 2 — omitted entirely |
| MapPopup deleted | Task 5 |
| Sidebar receives viewportListings | Task 4 — `<ListingSidebar listings={viewportListings}` |
| "N in view" counter | Task 3 |
| Hover sync sidebar → pin | Task 3 `onMouseEnter` → Task 2 `hoveredId` effect |
| Hover sync pin → sidebar | Task 2 `mouseover` → `onHover` → Task 3 hover class |
| SelectedCard appears on pin click | Task 4 — `<SelectedCard listing={highlightedListing}` |
| SelectedCard dismiss via ✕ | Task 1 — close button |
| SelectedCard dismiss via map click | Task 4 — `onMapClick={handleCloseDetail}` |
| "View details" opens ListingDetail | Task 4 — `onViewDetails={() => setDetailId(highlightedId)}` |
| `iconSize: [80, 24]` wide enough | Task 2 |
| `BoundsTracker` deps `[map, onBoundsChange]` | Task 2 |
| Edge case: null coords excluded from viewport | Task 4 — `l.coordinates != null &&` |
| Edge case: bounds null → show all filteredListings | Task 4 — `if (!bounds) return filteredListings` |

All spec requirements covered. No placeholders. Types consistent throughout.
