# Property Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive map view to the Property Dashboard using Leaflet + OpenStreetMap. Listings with exact coordinates get red pins; listings with only a district + landmark hint get orange pins at the resolved landmark; listings with no usable location data are excluded from the map.

**Architecture:** Two-phase approach: (1) extend the scrape pipeline to geocode landmark hints and store coordinates in MongoDB, (2) build the Next.js map page that reads pre-computed coordinates and renders them on a Leaflet map.

**Tech Stack:** Next.js 14 App Router, Leaflet 1.9 + react-leaflet + Leaflet.markercluster, OpenStreetMap tiles, TypeScript, Tailwind CSS.

---

## File Map

```
dashboard/
  app/
    dashboard/
      page.tsx          # Existing list view
      map/
        page.tsx        # NEW: map page (sidebar + Leaflet map)
    api/
      listings/
        top/route.ts    # Existing
        map/
          route.ts      # NEW: map-optimized listings endpoint
  components/
    FilterBar.tsx      # Existing — shared with map
    ListingCard.tsx    # Existing
    ListingDetail.tsx  # Existing
    MapPin.tsx         # NEW: marker component
    ListingSidebar.tsx # NEW: filter sidebar for map (extends FilterBar)
    MapView.tsx        # NEW: Leaflet map wrapper
  lib/
    types.ts           # Existing — add MapListing type
    mongodb.ts         # Existing
    mapUtils.ts        # NEW: coordinate type helpers

Project/
  Application/
    helpers/
      geocoding.py          # Existing — ViennaGeocoder
      __init__.py           # Modify — expose geocode_listing()
    main.py                 # Modify — call geocode_listing after save
  Domain/
    listing.py               # Existing — add coordinate fields
  Integration/
    mongodb_handler.py      # Modify — save coordinates/coordinate_source/landmark_hint
```

---

## Task 1: Add coordinate fields to Listing types

**Files:**
- Modify: `dashboard/lib/types.ts`

- [ ] **Step 1: Add MapListing interface to types.ts**

```typescript
// dashboard/lib/types.ts — add after TopListingsResponse

export type CoordinateSource = 'exact' | 'landmark' | 'none';

export interface MapListing {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  image_url: string | null;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
git add dashboard/lib/types.ts
git commit -m "feat(dashboard): add MapListing type and CoordinateSource"
```

---

## Task 2: Add coordinate fields to MongoDB listing documents

**Files:**
- Modify: `Project/Domain/listing.py` — add `coordinates`, `coordinate_source`, `landmark_hint` fields
- Modify: `Project/Integration/mongodb_handler.py` — save and query new fields

- [ ] **Step 1: Add fields to Listing dataclass**

```python
# Project/Domain/listing.py — add to Listing dataclass
coordinates: Optional['Coordinates'] = None
coordinate_source: Optional[str] = None  # 'exact' | 'landmark' | 'none'
landmark_hint: Optional[str] = None
```

Note: `Coordinates` is already imported from `Domain.location`.

- [ ] **Step 2: Modify mongodb_handler save method to accept coordinates**

Find `insert_listing` or `save_listing` method. The method already accepts a `listing: Dict`. Ensure it passes through `coordinates`, `coordinate_source`, and `landmark_hint` fields as-is (they're already part of the dict).

No code change needed if the handler just stores the dict as-is. Verify by reading the `insert_listing` method — it calls `collection.insert_one(listing)` with no field filtering.

- [ ] **Step 3: Commit**

```bash
git add Project/Domain/listing.py
git commit -m "feat: add coordinate_source and landmark_hint to Listing model"
```

---

## Task 3: Landmark hint extraction utility

**Files:**
- Create: `Project/Application/helpers/landmark_extractor.py`
- Test: `Tests/test_landmark_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_landmark_extractor.py
import pytest
from Application.helpers.landmark_extractor import extract_landmark_hint

class TestExtractLandmarkHint:
    def test_ubahn_pattern(self):
        result = extract_landmark_hint("3-Zi nahe Kettenbrückengasse U-Bahn")
        assert result == "Kettenbrückengasse U-Bahn, Wien, Austria"

    def test_strassenbahn_pattern(self):
        result = extract_landmark_hint("Wohnung in der Nähe von Pilgramgasse Straßenbahn")
        assert result == "Pilgramgasse, Wien, Austria"

    def test_no_hint_returns_none(self):
        result = extract_landmark_hint("Schöne 3-Zimmer-Wohnung in Margareten")
        assert result is None

    def test_empty_string(self):
        result = extract_landmark_hint("")
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_landmark_extractor.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# Project/Application/helpers/landmark_extractor.py
import re
from typing import Optional

UBAHN_PATTERNS = [
    re.compile(r'\bnahen?\s+(\w+\s+U-Bahn)', re.IGNORECASE),
    re.compile(r'\bnahe\s+(\w+\s+U-Bahn)', re.IGNORECASE),
    re.compile(r'\b(\w+\s+U-Bahn)\s+', re.IGNORECASE),
]

STRASSENBAHN_PATTERNS = [
    re.compile(r'\b(\w+\s+Straßenbahn)\b', re.IGNORECASE),
    re.compile(r'\bStraßenbahn\s+(\w+)', re.IGNORECASE),
    re.compile(r'\b(\w+)\s+Straßenbahn', re.IGNORECASE),
]

def extract_landmark_hint(text: str) -> Optional[str]:
    """Extract a landmark hint from listing title/description."""
    if not text:
        return None

    # Try U-Bahn patterns
    for pattern in UBAHN_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"{match.group(1)}, Wien, Austria"

    # Try Straßenbahn patterns
    for pattern in STRASSENBAHN_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"{match.group(1)}, Wien, Austria"

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Tests/test_landmark_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Project/Application/helpers/landmark_extractor.py Tests/test_landmark_extractor.py
git commit -m "feat: add landmark hint extraction for map geocoding"
```

---

## Task 4: Geocode listings at scrape time and store in MongoDB

**Files:**
- Modify: `Project/Application/main.py` — call geocode_listing after each listing is saved
- Modify: `Project/Application/helpers/geocoding.py` — add `geocode_listing` function
- Modify: `Project/Application/helpers/__init__.py` — export `geocode_listing`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_geocode_listing.py
import pytest
from unittest.mock import patch, MagicMock
from Application.helpers.geocoding import geocode_listing, ViennaGeocoder
from Domain.location import Coordinates

class TestGeocodeListing:
    @patch.object(ViennaGeocoder, 'geocode_address')
    def test_exact_address_geocodes_and_sets_source_exact(self, mock_geocode):
        mock_geocode.return_value = Coordinates(48.2082, 16.3738)
        listing = {
            'url': 'https://example.com',
            'title': 'Test',
            'address': 'Schottengasse 1, 1010 Wien',
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'exact'
        assert result['coordinates'] == {'lat': 48.2082, 'lon': 16.3738}
        mock_geocode.assert_called_once_with('Schottengasse 1, 1010 Wien')

    @patch.object(ViennaGeocoder, 'geocode_address')
    def test_landmark_hint_when_no_address(self, mock_geocode):
        mock_geocode.return_value = Coordinates(48.1967, 16.3400)
        listing = {
            'url': 'https://example.com',
            'title': 'Wohnung nahe Pilgramgasse U-Bahn',
            'address': None,
            'landmark_hint': 'Pilgramgasse U-Bahn, Wien, Austria',
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'landmark'
        assert result['coordinates'] == {'lat': 48.1967, 'lon': 16.3400}

    def test_no_location_data_sets_source_none(self):
        listing = {
            'url': 'https://example.com',
            'title': 'Wohnung in Wien',
            'address': None,
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'none'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Tests/test_geocode_listing.py -v`
Expected: FAIL — function not defined

- [ ] **Step 3: Write geocode_listing function**

```python
# In Project/Application/helpers/geocoding.py — add at end of file

def geocode_listing(listing: Dict) -> Dict:
    """
    Geocode a listing's location and store coordinates.
    Returns updated listing dict with coordinates, coordinate_source, landmark_hint.
    """
    from .landmark_extractor import extract_landmark_hint

    coordinates = listing.get('coordinates')
    coordinate_source = listing.get('coordinate_source')

    # Already geocoded — skip
    if coordinate_source in ('exact', 'landmark'):
        return listing

    geocoder = ViennaGeocoder()

    # Try exact address
    address = listing.get('address')
    if address:
        coords = geocoder.geocode_address(address)
        if coords:
            listing['coordinates'] = {'lat': coords.lat, 'lon': coords.lon}
            listing['coordinate_source'] = 'exact'
            return listing

    # Try landmark hint from title
    title = listing.get('title', '')
    hint = extract_landmark_hint(title)
    if hint:
        coords = geocoder.geocode_address(hint)
        if coords:
            listing['coordinates'] = {'lat': coords.lat, 'lon': coords.lon}
            listing['coordinate_source'] = 'landmark'
            listing['landmark_hint'] = hint.replace(', Wien, Austria', '')
            return listing

    # No usable location
    listing['coordinate_source'] = 'none'
    return listing
```

Also add to imports at top of geocoding.py:
```python
from typing import Dict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Tests/test_geocode_listing.py -v`
Expected: PASS

- [ ] **Step 5: Export geocode_listing from helpers __init__.py**

```python
# Project/Application/helpers/__init__.py — add export
from .geocoding import geocode_listing
```

- [ ] **Step 6: Hook into main.py scrape pipeline**

Read `Project/Application/main.py` to find where listings are saved to MongoDB. After `mongodb_handler.insert_listing(listing)` succeeds, call:

```python
from Application.helpers import geocode_listing
# After successful insert:
geocoded = geocode_listing(listing)
if geocoded.get('coordinate_source') != 'none':
    # Update with coordinates
    mongodb_handler.update_listing_coordinates(listing['url'], geocoded)
```

Note: You may need to add `update_listing_coordinates` to `mongodb_handler` — a method that does `collection.update_one({"url": url}, {"$set": {"coordinates": ..., "coordinate_source": ..., "landmark_hint": ...}})`. Or use the existing upsert pattern if one exists.

Read `main.py` first to find the exact insertion point and determine if a new handler method is needed.

- [ ] **Step 7: Commit**

```bash
git add Project/Application/helpers/geocoding.py Project/Application/helpers/__init__.py Project/Application/main.py Project/Integration/mongodb_handler.py
git commit -m "feat: geocode listings at scrape time and store coordinates"
```

---

## Task 5: Install Leaflet dependencies

**Files:**
- Modify: `dashboard/package.json`

- [ ] **Step 1: Install dependencies**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm install leaflet react-leaflet @react-leaflet/core leaflet.markercluster`
Run: `npm install -D @types/leaflet @types/leaflet.markercluster`

- [ ] **Step 2: Verify package.json**

The following should be in `dependencies`:
- `leaflet`: `^1.9.4`
- `react-leaflet`: `^4.2.1`
- `@react-leaflet/core`: `^2.1.0`
- `leaflet.markercluster`: `^1.5.3`

And in `devDependencies`:
- `@types/leaflet`: `^1.9.8`
- `@types/leaflet.markercluster`: `^1.5.4`

- [ ] **Step 3: Add leaflet CSS to globals.css**

```css
/* dashboard/app/globals.css — add */
@import 'leaflet/dist/leaflet.css';
@import 'leaflet.markercluster/dist/MarkerCluster.css';
@import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/app/globals.css
git commit -m "feat(dashboard): install Leaflet and react-leaflet"
```

---

## Task 6: New API route: GET /api/listings/map

**Files:**
- Create: `dashboard/app/api/listings/map/route.ts`

- [ ] **Step 1: Write the route**

```typescript
// dashboard/app/api/listings/map/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { db, ObjectId } from '@/lib/mongodb';
import { MapListing } from '@/lib/types';
import { Document, WithId } from 'mongodb';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200);
  const minScore = parseFloat(searchParams.get('min_score') || '0');
  const district = searchParams.get('district');

  try {
    const filter: Record<string, unknown> = {
      coordinate_source: { $in: ['exact', 'landmark'] },
    };

    if (minScore > 0) {
      filter.score = { $gte: minScore };
    }

    if (district) {
      filter.bezirk = district;
    }

    const listings = await db
      .collection<Document>('listings')
      .find(filter)
      .sort({ score: -1 })
      .limit(limit)
      .toArray();

    const result: MapListing[] = listings.map((l: WithId<Document>) => ({
      _id: l._id.toString(),
      title: l.title,
      url: l.url,
      source_enum: l.source_enum,
      bezirk: l.bezirk,
      price_total: l.price_total,
      area_m2: l.area_m2,
      rooms: l.rooms,
      score: l.score,
      image_url: l.image_url || null,
      coordinates: l.coordinates || null,
      coordinate_source: l.coordinate_source || 'none',
      landmark_hint: l.landmark_hint || null,
    }));

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/map]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts
git commit -m "feat(dashboard): add GET /api/listings/map endpoint"
```

---

## Task 7: MapView component

**Files:**
- Create: `dashboard/components/MapView.tsx`

- [ ] **Step 1: Write MapView component**

```tsx
// dashboard/components/MapView.tsx
'use client';

import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect } from 'react';

// Fix default marker icon (Leaflet + webpack issue)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const EXACT_COLOR = '#ef4444'; // red
const LANDMARK_COLOR = '#f97316'; // orange

function createPinIcon(color: string, isLandmark: boolean) {
  return L.divIcon({
    html: `<div style="
      background:${color};
      width:14px;height:14px;
      border-radius:50% 50% 0;
      transform:rotate(45deg);
      border:2px solid white;
      box-shadow:0 2px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 0],
    popupAnchor: [0, -10],
    className: '',
  });
}

interface FlyToProps {
  listing: MapListing | null;
}

function FlyTo({ listing }: FlyToProps) {
  const map = useMap();
  useEffect(() => {
    if (listing?.coordinates) {
      map.flyTo([listing.coordinates.lat, listing.coordinates.lon], 16, {
        duration: 0.8,
      });
    }
  }, [listing, map]);
  return null;
}

interface MapViewProps {
  listings: MapListing[];
  selectedListing: MapListing | null;
  onPinClick: (listing: MapListing) => void;
}

export function MapView({ listings, selectedListing, onPinClick }: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];

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

      <FlyTo listing={selectedListing} />

      {listings.map((listing) => {
        if (!listing.coordinates) return null;
        const isLandmark = listing.coordinate_source === 'landmark';
        return (
          <Marker
            key={listing._id}
            position={[listing.coordinates.lat, listing.coordinates.lon]}
            icon={createPinIcon(isLandmark ? LANDMARK_COLOR : EXACT_COLOR, isLandmark)}
            eventHandlers={{
              click: () => onPinClick(listing),
            }}
          >
            <Popup>
              <div className="text-sm min-w-[160px]">
                <p className="font-semibold">{listing.title}</p>
                <p className="text-blue-600 font-bold">
                  {listing.price_total ? `€${listing.price_total.toLocaleString()}` : 'N/A'}
                </p>
                <p className="text-gray-500 text-xs">
                  {listing.area_m2}m² · {listing.rooms} rooms · Score {listing.score}
                </p>
                {isLandmark && listing.landmark_hint && (
                  <p className="text-orange-500 text-xs mt-1">
                    ~ {listing.landmark_hint}
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/MapView.tsx
git commit -m "feat(dashboard): add MapView Leaflet component"
```

---

## Task 8: ListingSidebar component (extends FilterBar for map)

**Files:**
- Create: `dashboard/components/ListingSidebar.tsx`
- Create: `dashboard/components/MapLegend.tsx`

- [ ] **Step 1: Write MapLegend**

```tsx
// dashboard/components/MapLegend.tsx
export function MapLegend() {
  return (
    <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg px-3 py-2 text-xs z-[1000]">
      <p className="font-semibold mb-2">Legend</p>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm transform rotate-45 bg-red-500"></div>
          <span>Exact coordinates</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm transform rotate-45 bg-orange-500"></div>
          <span>District + landmark</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write ListingSidebar**

```tsx
// dashboard/components/ListingSidebar.tsx
'use client';

import React from 'react';
import { FilterBar } from './FilterBar';
import { MapListing } from '@/lib/types';

interface ListingSidebarProps {
  listings: MapListing[];
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  selectedId: string | null;
  onSelect: (listing: MapListing) => void;
}

export function ListingSidebar({
  listings,
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh,
  selectedId, onSelect,
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
        />
      </div>

      <div className="px-3 py-2 text-xs text-gray-500 font-medium">
        LISTINGS ({listings.length})
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 flex flex-col gap-2">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm">No listings match your filters.</p>
        ) : (
          listings.map((l) => (
            <div
              key={l._id}
              onClick={() => onSelect(l)}
              className={`bg-white rounded-lg border p-3 cursor-pointer transition-all text-xs ${
                selectedId === l._id
                  ? 'border-blue-500 ring-1 ring-blue-500'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-gray-900 truncate">{l.title || 'Untitled'}</p>
              <p className="text-blue-600 font-bold mt-1">
                {l.price_total ? `€${l.price_total.toLocaleString()}` : 'N/A'}
              </p>
              <p className="text-gray-500 mt-1">
                {l.area_m2}m² · {l.rooms} rooms
              </p>
              <div className="flex items-center gap-1 mt-2">
                <span className={`px-1.5 py-0.5 rounded text-white text-[10px] font-medium ${
                  l.coordinate_source === 'exact' ? 'bg-red-500' : 'bg-orange-500'
                }`}>
                  {l.coordinate_source === 'exact' ? 'Exact' : 'Landmark'}
                </span>
                {l.score && (
                  <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[10px]">
                    {l.score}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/ListingSidebar.tsx dashboard/components/MapLegend.tsx
git commit -m "feat(dashboard): add ListingSidebar and MapLegend components"
```

---

## Task 9: Map page

**Files:**
- Create: `dashboard/app/dashboard/map/page.tsx`
- Modify: `dashboard/app/layout.tsx` — add navigation link to map

- [ ] **Step 1: Write the map page**

```tsx
// dashboard/app/dashboard/map/page.tsx
'use client';

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ListingSidebar } from '@/components/ListingSidebar';
import { MapLegend } from '@/components/MapLegend';
import { MapListing } from '@/lib/types';

// Dynamic import to avoid SSR issues with Leaflet
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
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [minScore, setMinScore] = useState('0');
  const [district, setDistrict] = useState('');

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (minScore !== '0') params.set('min_score', minScore);
      if (district) params.set('district', district);

      const res = await fetch(`/api/listings/map?${params}`);
      const data = await res.json();
      setListings(data.listings ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district]);

  useEffect(() => { fetchListings(); }, [fetchListings]);

  const selectedListing = listings.find((l) => l._id === selectedId) ?? null;

  const handlePinClick = (listing: MapListing) => {
    window.location.href = `/dashboard/${listing._id}`;
  };

  const handleSidebarSelect = (listing: MapListing) => {
    setSelectedId(listing._id);
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="h-14 border-b border-gray-200 bg-white flex items-center px-4 shrink-0">
        <h1 className="text-base font-semibold text-gray-900">Property Map</h1>
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
    </div>
  );
}
```

- [ ] **Step 2: Update navigation in layout**

Read `dashboard/app/layout.tsx` and add a link to `/dashboard/map` in the header navigation alongside the existing Dashboard link.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/dashboard/map/page.tsx dashboard/app/layout.tsx
git commit -m "feat(dashboard): add /dashboard/map page with Leaflet map"
```

---

## Task 10: Backfill coordinates for existing listings

**Files:**
- Create: `Project/scripts/backfill_coordinates.py`

- [ ] **Step 1: Write backfill script**

```python
#!/usr/bin/env python3
"""
Backfill coordinate_source and coordinates for existing listings in MongoDB.
Run once: python Project/scripts/backfill_coordinates.py

Uses existing ViennaGeocoder to geocode addresses and landmark hints.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Application.helpers import geocode_listing
from Integration.mongodb_handler import MongoDBHandler
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def backfill():
    db = MongoDBHandler()
    if db.collection is None:
        logger.error("MongoDB not connected")
        return

    # Find listings missing coordinate_source
    cursor = db.collection.find({
        "coordinate_source": {"$exists": False}
    })

    total = 0
    updated = 0
    for listing in cursor:
        total += 1
        geocoded = geocode_listing(dict(listing))
        if geocoded.get('coordinate_source') != 'none':
            db.collection.update_one(
                {"_id": listing["_id"]},
                {"$set": {
                    "coordinates": geocoded.get('coordinates'),
                    "coordinate_source": geocoded.get('coordinate_source'),
                    "landmark_hint": geocoded.get('landmark_hint'),
                }}
            )
            updated += 1
        else:
            db.collection.update_one(
                {"_id": listing["_id"]},
                {"$set": {"coordinate_source": "none"}}
            )
            updated += 1

        if total % 50 == 0:
            logger.info(f"Processed {total} listings...")

    logger.info(f"Done. Processed {total} listings, updated {updated}.")

if __name__ == '__main__':
    backfill()
```

- [ ] **Step 2: Commit**

```bash
mkdir -p Project/scripts
git add Project/scripts/backfill_coordinates.py
git commit -m "script: add backfill_coordinates for existing listings"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| Leaflet + OSM map | Task 5, 7 |
| /dashboard/map route | Task 9 |
| Filter sidebar synced with map | Task 8 |
| Red pin (exact coords) / Orange pin (landmark) | Task 7 |
| Cluster at zoom-out | Task 5 (leaflet.markercluster) |
| Pin click → detail page | Task 9 |
| Pin hover → popup | Task 7 |
| /api/listings/map endpoint | Task 6 |
| Geocode at scrape time | Task 4 |
| Landmark hint extraction | Task 3 |
| Pre-geocode existing listings | Task 10 |
| Hidden from map if no location | Task 6 filter |
| Legend overlay | Task 8 |
| Mobile sidebar (slide-out) | **Not implemented** — defer to Task 11 |
| District polygon highlight | Out of scope |

---

## Type Consistency Check

- `MapListing.coordinate_source`: values are `'exact' | 'landmark' | 'none'` — matches backend Python values
- `MapListing.coordinates`: `{ lat: number; lon: number } | null` — matches MongoDB storage `{ lat, lon }`
- `geocode_listing()` returns `Dict` — keys `coordinates`, `coordinate_source`, `landmark_hint`
- MongoDB update in Task 4 uses exact field names matching the TypeScript interface

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
