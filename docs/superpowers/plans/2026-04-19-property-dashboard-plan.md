# Property Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Personal Next.js dashboard on Vercel browsing top-scored listings from MongoDB, with drill-down detail and URL rechecking.

**Architecture:** Next.js App Router frontend with API routes that query the existing MongoDB. The dashboard is a standalone Next.js app in `dashboard/` subdirectory, connecting directly to MongoDB via `MONGODB_URI`.

**Tech Stack:** Next.js 14 (App Router), Tailwind CSS, MongoDB driver, deployed on Vercel free tier.

---

## File Structure

```
dashboard/                    # New Next.js app (gitignored from root, or separate repo)
├── app/
│   ├── api/
│   │   └── listings/
│   │       ├── top/
│   │       │   └── route.ts         # GET /api/listings/top
│   │       └── [id]/
│   │           ├── route.ts         # GET /api/listings/[id]
│   │           └── check/
│   │               └── route.ts     # POST /api/listings/[id]/check
│   ├── dashboard/
│   │   ├── page.tsx                 # List view
│   │   └── [id]/
│   │       └── page.tsx            # Detail view
│   ├── layout.tsx
│   └── page.tsx                    # Redirect to /dashboard
├── components/
│   ├── ListingCard.tsx             # List card component
│   ├── ListingDetail.tsx           # Detail modal/component
│   ├── FilterBar.tsx                # Filter controls
│   └── ScoreBadge.tsx              # Score display badge
├── lib/
│   ├── mongodb.ts                  # MongoDB client singleton
│   └── types.ts                   # Shared TypeScript types
├── package.json
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json

Project/Integration/mongodb_handler.py  # Modified: add get_listing_by_id, update_url_is_valid
```

**MongoDB field names confirmed from codebase:**
- `score` — listing score (float)
- `processed_at` — unix timestamp of when listing was scraped
- `url` — listing URL string
- `source_enum` — Source enum value ("willhaben", "immo_kurier", "derstandard", "unknown")
- `bezirk` — district string (e.g., "02")
- All other fields from `Project/Domain/listing.py` dataclass

---

## Task 1: Scaffold Next.js App

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/next.config.js`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/tsconfig.json`

- [ ] **Step 1: Create `dashboard/package.json`**

```json
{
  "name": "immo-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.0",
    "react": "^18",
    "react-dom": "^18",
    "mongodb": "^6"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "tailwindcss": "^3.4.0",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^8",
    "eslint-config-next": "14.2.0"
  }
}
```

- [ ] **Step 2: Create `dashboard/next.config.js`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
};

module.exports = nextConfig;
```

- [ ] **Step 3: Create `dashboard/tailwind.config.ts`**

```ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 4: Create `dashboard/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ['./*'] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 5: Create PostCSS config `dashboard/postcss.config.js`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create `dashboard/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Create `dashboard/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Immo Scouter Dashboard',
  description: 'Browse top property listings',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create `dashboard/app/page.tsx` (redirect root to dashboard)**

```tsx
import { redirect } from 'next/navigation';

export default function Home() {
  redirect('/dashboard');
}
```

- [ ] **Step 9: Install dependencies**

Run: `cd dashboard && npm install`
Expected: node_modules created, package-lock.json generated

- [ ] **Step 10: Commit**

```bash
git add dashboard/
git commit -m "feat: scaffold Next.js dashboard app"
```

---

## Task 2: MongoDB Types and Client

**Files:**
- Create: `dashboard/lib/types.ts`
- Create: `dashboard/lib/mongodb.ts`

- [ ] **Step 1: Create `dashboard/lib/types.ts`**

```ts
export interface ListingBase {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  processed_at: number | null;
  image_url: string | null;
}

export interface ListingDetail extends ListingBase {
  address: string | null;
  year_built: number | null;
  floor: number | null;
  condition: string | null;
  heating: string | null;
  parking: string | null;
  betriebskosten: number | null;
  energy_class: string | null;
  hwb_value: number | null;
  fgee_value: number | null;
  rooms: number | null;
  calculated_monatsrate: number | null;
  total_monthly_cost: number | null;
  ubahn_walk_minutes: number | null;
  school_walk_minutes: number | null;
  infrastructure_distances: Record<string, unknown>;
  score_breakdown?: Record<string, number>;
  url_is_valid?: boolean;
}

export interface TopListingsResponse {
  listings: ListingBase[];
  total: number;
}
```

- [ ] **Step 2: Create `dashboard/lib/mongodb.ts`**

```ts
import { MongoClient, ObjectId } from 'mongodb';

const MONGODB_URI = process.env.MONGODB_URI!;

let cached = (global as { mongodb?: { client: MongoClient; db: ReturnType<MongoClient['database']> } }).mongodb;

if (!cached) {
  const client = new MongoClient(MONGODB_URI);
  cached = { client, db: client.db('immo') };
  (global as { mongodb?: typeof cached }).mongodb = cached;
}

export const { client, db } = cached;
export { ObjectId };
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/
git commit -m "feat: add MongoDB types and client"
```

---

## Task 3: API Routes

**Files:**
- Create: `dashboard/app/api/listings/top/route.ts`
- Create: `dashboard/app/api/listings/[id]/route.ts`
- Create: `dashboard/app/api/listings/[id]/check/route.ts`

- [ ] **Step 1: Create `dashboard/app/api/listings/top/route.ts`**

```ts
import { NextRequest, NextResponse } from 'next/server';
import { db, ObjectId } from '@/lib/mongodb';

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100);
  const minScore = parseFloat(searchParams.get('min_score') || '0');
  const district = searchParams.get('district');

  try {
    const cutoff = Date.now() - SEVEN_DAYS_MS;

    const filter: Record<string, unknown> = {
      processed_at: { $gte: cutoff / 1000 },
    };

    if (minScore > 0) {
      filter.$or = [
        { score: { $gte: minScore } },
        { score: null },
      ];
    }

    if (district) {
      filter.bezirk = district;
    }

    const listings = await db
      .collection('listings')
      .find(filter)
      .sort({ score: -1, processed_at: -1 })
      .limit(limit)
      .toArray();

    const result = listings.map((l) => ({
      _id: l._id.toString(),
      title: l.title,
      url: l.url,
      source_enum: l.source_enum,
      bezirk: l.bezirk,
      price_total: l.price_total,
      area_m2: l.area_m2,
      rooms: l.rooms,
      score: l.score,
      processed_at: l.processed_at,
      image_url: l.image_url || l.minio_image_path || null,
      url_is_valid: l.url_is_valid !== false,
    }));

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/top]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 2: Create `dashboard/app/api/listings/[id]/route.ts`**

```ts
import { NextRequest, NextResponse } from 'next/server';
import { db, ObjectId } from '@/lib/mongodb';

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const listing = await db.collection('listings').findOne({
      _id: new ObjectId(params.id),
    });

    if (!listing) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    // Flatten for response
    const result: Record<string, unknown> = { _id: listing._id.toString() };
    for (const [key, value] of Object.entries(listing)) {
      if (key === '_id') continue;
      if (value instanceof ObjectId) {
        result[key] = value.toString();
      } else {
        result[key] = value;
      }
    }

    return NextResponse.json(result);
  } catch (err) {
    console.error('[/api/listings/[id]]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 3: Create `dashboard/app/api/listings/[id]/check/route.ts`**

```ts
import { NextRequest, NextResponse } from 'next/server';
import { db, ObjectId } from '@/lib/mongodb';

async function checkUrl(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: 'HEAD', redirect: 'follow' });
    return res.ok;
  } catch {
    return false;
  }
}

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const listing = await db.collection('listings').findOne({
      _id: new ObjectId(params.id),
    });

    if (!listing) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const isValid = await checkUrl(listing.url);

    await db.collection('listings').updateOne(
      { _id: new ObjectId(params.id) },
      { $set: { url_is_valid: isValid } }
    );

    return NextResponse.json({ url_is_valid: isValid });
  } catch (err) {
    console.error('[/api/listings/[id]/check]', err);
    return NextResponse.json({ error: 'Check failed' }, { status: 500 });
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/api/
git commit -m "feat: add listings API routes (top, detail, check)"
```

---

## Task 4: Dashboard List View

**Files:**
- Create: `dashboard/components/ListingCard.tsx`
- Create: `dashboard/components/ScoreBadge.tsx`
- Create: `dashboard/components/FilterBar.tsx`
- Create: `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Create `dashboard/components/ScoreBadge.tsx`**

```tsx
import React from 'react';

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const color =
    score >= 70 ? 'bg-green-100 text-green-800' :
    score >= 50 ? 'bg-yellow-100 text-yellow-800' :
    'bg-red-100 text-red-800';

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}
```

- [ ] **Step 2: Create `dashboard/components/ListingCard.tsx`**

```tsx
'use client';

import React from 'react';
import { ListingBase } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const sourceLabel: Record<string, string> = {
    willhaben: 'WH',
    immo_kurier: 'IK',
    derstandard: 'DS',
    unknown: '?',
  };

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="cursor-pointer bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md hover:border-gray-300 transition-all duration-200"
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-medium text-gray-900 line-clamp-2 flex-1 mr-2">
          {listing.title || 'No title'}
        </h3>
        <ScoreBadge score={listing.score} />
      </div>

      <div className="space-y-1 text-sm text-gray-600">
        {listing.price_total && (
          <p className="font-semibold text-gray-900">
            €{listing.price_total.toLocaleString('de-AT')}
          </p>
        )}
        <p>
          {listing.area_m2 ?? '–'} m² &bull; {listing.rooms ?? '–'} rooms
          {listing.bezirk && ` &bull; District ${listing.bezirk}`}
        </p>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {sourceLabel[listing.source_enum] ?? '?'}
        </span>
        {listing.processed_at && (
          <span className="text-xs text-gray-400">
            {new Date(listing.processed_at * 1000).toLocaleDateString('de-AT')}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `dashboard/components/FilterBar.tsx`**

```tsx
'use client';

import React from 'react';

interface FilterBarProps {
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
}

export function FilterBar({
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Min Score</label>
        <input
          type="number"
          min="0"
          max="100"
          value={minScore}
          onChange={(e) => onMinScoreChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">District</label>
        <input
          type="text"
          placeholder="e.g. 02"
          value={district}
          onChange={(e) => onDistrictChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <button
        onClick={onRefresh}
        className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
      >
        Refresh
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Create `dashboard/app/dashboard/page.tsx`**

```tsx
'use client';

import React, { useState, useCallback } from 'react';
import { ListingCard } from '@/components/ListingCard';
import { FilterBar } from '@/components/FilterBar';
import { ListingDetail } from '@/components/ListingDetail';
import { ListingBase } from '@/lib/types';

export default function DashboardPage() {
  const [listings, setListings] = useState<ListingBase[]>([]);
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

      const res = await fetch(`/api/listings/top?${params}`);
      const data = await res.json();
      setListings(data.listings ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district]);

  React.useEffect(() => { fetchListings(); }, [fetchListings]);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Top Property Picks</h1>
          <p className="text-sm text-gray-500 mt-1">Last 7 days, sorted by score</p>
        </header>

        <FilterBar
          minScore={minScore}
          onMinScoreChange={setMinScore}
          district={district}
          onDistrictChange={setDistrict}
          onRefresh={fetchListings}
        />

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

      {selectedId && (
        <ListingDetail
          id={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/ dashboard/app/dashboard/
git commit -m "feat: add dashboard list view with filters"
```

---

## Task 5: Detail View

**Files:**
- Create: `dashboard/components/ListingDetail.tsx`
- Create: `dashboard/app/dashboard/[id]/page.tsx` (optional deep-link)

- [ ] **Step 1: Create `dashboard/components/ListingDetail.tsx`**

```tsx
'use client';

import React, { useEffect, useState } from 'react';
import { ListingDetail as ListingDetailType } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingDetailProps {
  id: string;
  onClose: () => void;
}

export function ListingDetail({ id, onClose }: ListingDetailProps) {
  const [listing, setListing] = useState<ListingDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [urlValid, setUrlValid] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`/api/listings/${id}`)
      .then((r) => r.json())
      .then(setListing)
      .finally(() => setLoading(false));
  }, [id]);

  const handleRecheck = async () => {
    setChecking(true);
    try {
      const res = await fetch(`/api/listings/${id}/check`, { method: 'POST' });
      const data = await res.json();
      setUrlValid(data.url_is_valid);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : listing ? (
          <>
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <ScoreBadge score={listing.score} />
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              <h2 className="text-xl font-bold text-gray-900">{listing.title || 'No title'}</h2>

              <div className="grid grid-cols-2 gap-4 text-sm">
                {listing.price_total && (
                  <div><span className="font-medium">Price:</span> €{listing.price_total.toLocaleString('de-AT')}</div>
                )}
                {listing.area_m2 && <div><span className="font-medium">Area:</span> {listing.area_m2} m²</div>}
                {listing.rooms && <div><span className="font-medium">Rooms:</span> {listing.rooms}</div>}
                {listing.bezirk && <div><span className="font-medium">District:</span> {listing.bezirk}</div>}
                {listing.year_built && <div><span className="font-medium">Year Built:</span> {listing.year_built}</div>}
                {listing.floor && <div><span className="font-medium">Floor:</span> {listing.floor}</div>}
                {listing.condition && <div><span className="font-medium">Condition:</span> {listing.condition}</div>}
                {listing.heating && <div><span className="font-medium">Heating:</span> {listing.heating}</div>}
                {listing.energy_class && <div><span className="font-medium">Energy Class:</span> {listing.energy_class}</div>}
                {listing.hwb_value && <div><span className="font-medium">HWB:</span> {listing.hwb_value}</div>}
                {listing.betriebskosten && <div><span className="font-medium"> Betriebskosten:</span> €{listing.betriebskosten}</div>}
                {listing.ubahn_walk_minutes != null && <div><span className="font-medium">U-Bahn:</span> {listing.ubahn_walk_minutes} min</div>}
              </div>

              {listing.infrastructure_distances && Object.keys(listing.infrastructure_distances).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-1">Infrastructure</h3>
                  <div className="text-sm text-gray-600">
                    {Object.entries(listing.infrastructure_distances).map(([k, v]) => (
                      <p key={k}>{k}: {String(v)}</p>
                    ))}
                  </div>
                </div>
              )}

              {listing.score_breakdown && Object.keys(listing.score_breakdown).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-1">Score Breakdown</h3>
                  <div className="text-sm text-gray-600">
                    {Object.entries(listing.score_breakdown).map(([k, v]) => (
                      <p key={k}>{k}: {typeof v === 'number' ? v.toFixed(1) : v}</p>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <a
                  href={listing.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Open Original
                </a>
                <button
                  onClick={handleRecheck}
                  disabled={checking}
                  className="px-4 py-2 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {checking ? 'Checking...' : 'Recheck Availability'}
                </button>
                {urlValid !== null && (
                  <span className={`px-3 py-2 text-sm rounded-lg ${urlValid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {urlValid ? 'Available' : 'Unavailable'}
                  </span>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="p-8 text-center text-gray-500">Listing not found</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/ListingDetail.tsx
git commit -m "feat: add listing detail modal with recheck"
```

---

## Task 6: Vercel Config & Deployment

**Files:**
- Create: `dashboard/.env.local.example`
- Modify: `.gitignore` (add `dashboard/node_modules/`, `dashboard/.next/`)

- [ ] **Step 1: Create `dashboard/.env.local.example`**

```
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/immo
```

- [ ] **Step 2: Update `.gitignore`**

Add to `.gitignore`:
```
dashboard/node_modules/
dashboard/.next/
dashboard/.env.local
```

- [ ] **Step 3: Create Vercel deployment guide `docs/superpowers/plans/2026-04-19-vercel-deployment.md`**

```markdown
# Vercel Deployment Guide

## Prerequisites
- Vercel account connected to GitHub
- MongoDB Atlas cluster (or public-facing MongoDB)

## Steps

1. **Push dashboard to GitHub**
   The `dashboard/` folder should be in the repo root.

2. **Connect to Vercel**
   - Go to vercel.com → New Project
   - Import the repo
   - Set root directory to `dashboard/`
   - Add environment variable: `MONGODB_URI` = your Atlas connection string

3. **Deploy**
   - Vercel auto-detects Next.js
   - Deploy — should complete in ~2 minutes

4. **Custom Domain (optional)**
   - Add domain in Vercel project settings

## MongoDB Atlas Setup

If using MongoDB Atlas (free tier M0):
1. Create cluster at atlas.mongodb.com
2. Add IP `0.0.0.0/0` to Network Access
3. Create database user
4. Get connection string: `mongodb+srv://user:pass@cluster.mongodb.net/immo`
5. Set `MONGODB_URI` in Vercel env vars
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore dashboard/.env.local.example docs/
git commit -m "docs: add Vercel deployment guide and env example"
```

---

## Self-Review Checklist

- [ ] All API routes return JSON, handle errors with proper status codes
- [ ] `url_is_valid` field added to MongoDB on recheck (new field, no migration needed)
- [ ] Tailwind classes use standard palette (gray, blue, green, yellow, red) — no custom colors needed
- [ ] Responsive grid: 1-col mobile, 2-col tablet, 3-col desktop
- [ ] `dashboard/` folder is gitignored (node_modules, .next, .env.local)
- [ ] `MONGODB_URI` is the only required env var
- [ ] No authentication — personal use only (per spec)
