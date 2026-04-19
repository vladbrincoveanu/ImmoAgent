# Property Map — Design Spec

## Overview

Add an interactive map view to the Property Dashboard that plots listings on a free OpenStreetMap base layer using Leaflet. Listings with exact coordinates get precise pins; listings with only a district + landmark hint get pins at the resolved landmark; listings with no usable location data are excluded from the map.

The map is a top-level route (`/map`) with a synchronized filter sidebar. It shares the same filter model as the list view (`/dashboard`).

## Stack

- **Map library:** Leaflet 1.9 + OpenStreetMap tiles (no API key, free)
- **Frontend:** Next.js App Router (same as dashboard)
- **Map clustering:** Leaflet.markercluster plugin
- **Geocoding:** Nominatim (OpenStreetMap) — called at scrape time, not at runtime

## Architecture

### New Routes

| Route | Purpose |
|-------|---------|
| `/dashboard/map` | Map view — Leaflet map + filter sidebar |
| `/api/listings/map` | Listings optimized for map (includes coordinates, coordinate_source) |

### Coordinate Source

Each listing can have one of three coordinate sources:

| Source | Description | Map Treatment |
|--------|-------------|---------------|
| `exact` | Full address was geocoded | Red pin at exact lat/lon |
| `landmark` | District + landmark hint was geocoded | Orange pin at landmark coordinates |
| `none` | No usable location data | Hidden from map |

### Geocoding at Scrape Time

During the scraping pipeline (in `main.py` or the individual scrapers), after a listing is saved:

1. If the listing has an exact address → geocode via `ViennaGeocoder.geocode_address()` → store as `coordinates` with `coordinate_source: 'exact'`
2. If the listing has no exact address but has a district + landmark hint (e.g., "near Kettenbrückengasse U-Bahn") → extract the landmark → geocode via Nominatim → store as `coordinates` with `coordinate_source: 'landmark'`, store the landmark text in `landmark_hint`
3. If neither is available → store no coordinates, `coordinate_source: 'none'`

Geocoding happens once at scrape time. The map reads pre-computed coordinates — no runtime API calls.

> **Note:** The existing `ViennaGeocoder` in `Project/Application/helpers/geocoding.py` already implements `geocode_address()` using Nominatim. This logic should be extracted/reused rather than rewritten.

### MongoDB Schema Additions

```typescript
interface ListingCoordinates {
  lat: number;
  lon: number;
}

interface Listing {
  // ... existing fields ...

  // New fields:
  coordinates?: ListingCoordinates;   // null if coordinate_source === 'none'
  coordinate_source?: 'exact' | 'landmark' | 'none';
  landmark_hint?: string;             // e.g., "near Kettenbrückengasse U-Bahn"
}
```

### API Response: `/api/listings/map`

```typescript
// GET /api/listings/map?district=05&min_score=70&buyer_profile=owner_occupier&limit=50

interface MapListing {
  id: string;                    // MongoDB ObjectId
  title: string;
  price_total: number;
  area_m2: number;
  rooms: number;
  score: number;
  bezirk: string;
  source: string;
  image_url?: string;
  coordinates?: {
    lat: number;
    lon: number;
  };
  coordinate_source: 'exact' | 'landmark' | 'none';
  landmark_hint?: string;
}
```

The endpoint filters to only listings with `coordinate_source !== 'none'` and returns the lightweight `MapListing` shape (no full detail payload needed for map pins).

## Frontend

### Page: `/dashboard/map`

Layout: sidebar (280px) + map (remaining width), full viewport height.

```
┌──────────────────────────────────────────────────────┐
│  Property Scouter          [Dashboard] [Map]        │
├──────────────┬───────────────────────────────────────┤
│  FILTERS     │                                       │
│  District    │                                       │
│  [05    x]   │         🗺️  LEAFLET MAP               │
│  Min Score   │         (OSM tiles)                   │
│  [70]        │                                       │
│  Profile     │    📍 red pin (exact coords)          │
│  [OwnerOcc]  │    📍 orange pin (landmark)           │
│              │                                       │
│  LISTINGS    │                        [Legend]       │
│  (12)        │                        [zoom +/-]     │
│  ┌─────────┐ │                                       │
│  │Listing 1│ │                                       │
│  └─────────┘ │                                       │
│  ┌─────────┐ │                                       │
│  │Listing 2│ │                                       │
│  └─────────┘ │                                       │
└──────────────┴───────────────────────────────────────┘
```

### Sidebar Behavior

- **Filters:** same controls as `/dashboard` — district multi-select, min-score slider, buyer profile dropdown. Changing any filter refetches both the list and map data.
- **List preview:** scrollable list of the same listings shown on the map. Clicking a list item highlights it and flies the map to that pin.
- **Responsive:** on mobile (<768px), sidebar collapses to a slide-out panel triggered by a "Filters" button.

### Map Behavior

1. On load, fetch `/api/listings/map` with current filters → plot pins
2. **Exact coords** → red pin (`#ef4444`) at lat/lon
3. **Landmark** → orange pin (`#f97316`) at geocoded landmark coords. Show `landmark_hint` in pin tooltip.
4. **Clustering** → use `Leaflet.markercluster`:
   - Stacked pins when zoomed in (slight offset to prevent perfect overlap)
   - Cluster bubbles at zoomed-out levels showing count
5. **Pin click** → navigate to `/dashboard/[id]` (full detail view)
6. **Pin hover** → popup with listing summary (title, price, score, source badge)
7. **Empty state:** if no listings pass filters, show a centered message on the map area: "No listings match your filters"

### Legend

Fixed bottom-left overlay on the map:
- 🔴 Red pin — Exact coordinates (full address geocoded)
- 🟠 Orange pin — Approximate (district + landmark hint geocoded)
- Cluster bubble — Multiple listings at one location

## Module Design

### Module: Geocoding at Scrape Time
- **Responsibility:** Extract location hints from raw listings and resolve to coordinates at scrape time
- **Interface:** Called after listing is saved in `mongodb_handler.save_listing()` or in `Application.main`
- **Dependencies:** `ViennaGeocoder.geocode_address()`, Nominatim API
- **Size target:** ~60 lines — new utility function that wraps existing geocoder

### Module: `POST /api/listings/map`
- **Responsibility:** Return map-optimized listing data (lightweight, coordinates included, excludes `coordinate_source === 'none'`)
- **Interface:** Query params (district, min_score, buyer_profile, limit) → `MapListing[]`
- **Dependencies:** MongoDB via `mongodb_handler`
- **Size target:** ~25 lines

### Module: Dashboard Map Page (`/dashboard/map`)
- **Responsibility:** Full-page map view with sidebar filters and list preview
- **Interface:** Reads filters from URL params, fetches `/api/listings/map`
- **Dependencies:** Next.js, Leaflet, Leaflet.markercluster
- **Size target:** ~200 lines (page component + sub-components)

### Module: Map Pin Component
- **Responsibility:** Render a single marker with correct color, tooltip, and click handler
- **Interface:** Props: `MapListing`, `onClick` callback
- **Dependencies:** Leaflet
- **Size target:** ~40 lines

### Module: Filter Sidebar
- **Responsibility:** Unified filter controls + list preview, emits filter changes to parent
- **Interface:** Props: `onFilterChange` callback, emits filter state
- **Dependencies:** Next.js, Tailwind CSS
- **Size target:** ~150 lines

## Geocoding Workflow Detail

### Step 1 — Extract from raw listing

After a scraper returns a listing, before saving to MongoDB:

```python
# Pseudocode
listing = scraped_listing

if listing.address:
    coords = geocoder.geocode_address(listing.address)
    if coords:
        listing.coordinates = coords
        listing.coordinate_source = 'exact'
    else:
        # Fall through to landmark check
        pass

if not listing.coordinates and listing.landmark_hint:
    # landmark_hint is derived from title/description by a heuristic
    # e.g., "3-Zi nahe Kettenbrückengasse" → "Kettenbrückengasse U-Bahn"
    coords = geocoder.geocode_address(listing.landmark_hint + ", Wien, Austria")
    if coords:
        listing.coordinates = coords
        listing.coordinate_source = 'landmark'

if not listing.coordinates:
    listing.coordinate_source = 'none'
```

### Step 2 — Landmark Hint Extraction

A lightweight heuristic parses the listing title/description for landmark patterns:
- "nahe [X] U-Bahn" → landmark = "[X] U-Bahn, Wien"
- "in der Nähe von [X] Straßenbahn" → landmark = "[X], Wien"
- "[X] in [District]" (without street address) → landmark = district center

This is a best-effort pattern match — it does not need to be perfect. Listings that don't match are marked `coordinate_source: 'none'`.

### Step 3 — Persist to MongoDB

The `mongodb_handler.save_listing()` method stores `coordinates`, `coordinate_source`, and `landmark_hint` alongside the existing listing fields.

## Anti-Goals (Out of Scope)

- Routing/directions between listings
- Drawing district polygons on the map
- Geocoding at runtime (on map load)
- Satellite/map style switching
- Offline map tiles
- Exporting map as image
