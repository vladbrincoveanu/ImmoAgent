# Map Pin Preview Popup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal text-only map pin popup with an enriched property preview card showing image, score badge, source badge, title, price, area, rooms, district, and a "View Details →" CTA.

**Architecture:** Create a new `MapPopup.tsx` component that receives a `MapListing` and renders the enriched card. Modify `MapView.tsx` to use `<MapPopup>` inside the `<Popup>` instead of inline JSX.

**Tech Stack:** Next.js 14 App Router, TypeScript, react-leaflet, Tailwind CSS

---

## Task 1: Create MapPopup.tsx

**Files:**
- Create: `dashboard/components/MapPopup.tsx`

- [ ] **Step 1: Write the MapPopup component**

Create `/Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/components/MapPopup.tsx` with the following content:

```tsx
'use client';

import React, { useState } from 'react';
import { MapListing } from '@/lib/types';

interface MapPopupProps {
  listing: MapListing;
  onViewDetails: (id: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  willhaben: 'WH',
  immo_kurier: 'IK',
  derstandard: 'DS',
  unknown: '?',
};

export function MapPopup({ listing, onViewDetails }: MapPopupProps) {
  const [imageError, setImageError] = useState(false);

  const hasImage = listing.image_url && !imageError;

  return (
    <div className="min-w-[240px] bg-white rounded-lg overflow-hidden font-dm-sans">
      {/* Image area */}
      <div className="relative aspect-[16/10] bg-warm-bg overflow-hidden">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property image'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-border">
            <svg className="w-8 h-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
            </svg>
          </div>
        )}

        {/* Score badge — top right */}
        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-accent">
              {listing.score}
            </span>
          </div>
        )}

        {/* Source badge — bottom left */}
        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-heading bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      {/* Details area */}
      <div className="p-3">
        <h3 className="font-medium text-heading line-clamp-2 text-sm leading-snug mb-1">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-heading text-sm mb-1">
          {listing.price_total != null
            ? `${listing.price_is_estimated ? '~' : ''}€${listing.price_total.toLocaleString('de-AT')}`
            : 'Price on request'}
        </p>

        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs text-muted">
            {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
            {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
          </div>
          {listing.bezirk && (
            <span className="text-[10px] font-medium text-muted bg-warm-bg px-1.5 py-0.5 rounded">
              {listing.bezirk}
            </span>
          )}
        </div>

        {/* View Details CTA */}
        <button
          onClick={() => onViewDetails(listing._id)}
          className="text-xs text-blue-600 hover:text-blue-700 cursor-pointer transition-colors duration-150"
        >
          View Details →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build compiles**

Run in `/Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard`:
```bash
npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/MapPopup.tsx && git commit -m "feat(dashboard): add MapPopup component for enriched map pin preview"
```

---

## Task 2: Integrate MapPopup into MapView

**Files:**
- Modify: `dashboard/components/MapView.tsx:91-109` (the Popup block)

- [ ] **Step 1: Read current MapView.tsx Popup section**

Read `/Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/components/MapView.tsx`. The Popup block (around lines 91-109) currently is:

```tsx
<Popup>
  <div className="text-sm min-w-[160px] font-dm-sans">
    <p className="font-bold text-heading">{listing.title}</p>
    <p className="text-accent font-bold">
      {listing.price_total != null
        ? `${listing.price_is_estimated ? '~' : ''}€${listing.price_total.toLocaleString()}`
        : 'N/A'}
    </p>
    <p className="text-gray-500 text-xs">
      {listing.area_m2}m² · {listing.rooms} rooms · Score {listing.score}
    </p>
    {isLandmark && listing.landmark_hint && (
      <p className="text-orange-500 text-xs mt-1">~ {listing.landmark_hint}</p>
    )}
    {isDistrict && (
      <p className="text-blue-400 text-xs mt-1">~ District centroid (approx.)</p>
    )}
  </div>
</Popup>
```

- [ ] **Step 2: Import MapPopup at top of file**

Find the existing `import` lines in MapView.tsx (around line 3-6):

```tsx
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect } from 'react';
```

Add `MapPopup` to the component imports:

```tsx
import { MapPopup } from '@/components/MapPopup';
```

- [ ] **Step 3: Replace the Popup JSX**

Replace the entire `<Popup>...</Popup>` block with:

```tsx
<Popup>
  <MapPopup
    listing={listing}
    onViewDetails={(id) => {
      window.location.href = `/dashboard/${id}`;
    }}
  />
</Popup>
```

- [ ] **Step 4: Verify build compiles**

Run in `/Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard`:
```bash
npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/MapView.tsx && git commit -m "feat(dashboard): use MapPopup in map pin Popup for enriched preview"
```

---

## Final Verification

- [ ] **Step 1: Full build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build
```

Expected: all routes compile, no TypeScript errors.

- [ ] **Step 2: Push to remote**

```bash
git push origin main
```
