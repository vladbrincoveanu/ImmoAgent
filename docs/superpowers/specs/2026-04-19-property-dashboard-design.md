# Property Dashboard — Design Spec

## Overview

A personal web dashboard to browse top-scored property listings from the existing MongoDB, with drill-down detail view and URL availability rechecking.

## Stack

- **Frontend/Backend:** Next.js (App Router) on Vercel
- **Database:** Existing MongoDB (Docker or Atlas)
- **Styling:** Tailwind CSS

## Architecture

### API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/listings/top` | GET | Top picks by score, last 7 days, url_is_valid=true |
| `/api/listings/[id]` | GET | Single listing full detail |
| `/api/listings/[id]/check` | POST | Re-ping listing URL, update url_is_valid in MongoDB |

### Data Flow

1. User opens dashboard → fetches `/api/listings/top`
2. List view renders cards sorted by score descending
3. User clicks card → opens detail view (modal or route)
4. User clicks "Recheck availability" → POST to `/api/listings/[id]/check`
5. API pings listing URL, updates `url_is_valid` in MongoDB, returns result

### MongoDB Schema

No schema changes. Query existing `listings` collection:

- `url_is_valid: true` for availability filter
- `processed_at` for date filtering (last 7 days)
- `total_score` or `score` for ranking
- All other fields from existing `Listing` dataclass

## Frontend

### Pages

1. **`/dashboard`** — List view
   - Filter bar: buyer profile, min-score, district
   - Listing cards: title, price, area, rooms, score badge, bezirk, source, scraped date
   - Sorted by score descending
   - Responsive: 1-col mobile, 2-col tablet, 3-col desktop

2. **`/dashboard/[id]`** (or modal) — Detail view
   - All listing fields
   - Score breakdown
   - Images
   - Infrastructure distances / coordinates if available
   - "Open original" button → listing URL
   - "Recheck availability" button

### API Response Shapes

**List item:**
```json
{
  "id": "mongodb_object_id",
  "title": "3-Zimmer-Wohnung in Leopoldstadt",
  "url": "https://www.willhaben.at/...",
  "price_total": 450000,
  "area_m2": 75,
  "rooms": 3,
  "bezirk": "02",
  "score": 78.5,
  "source": "willhaben",
  "image_url": "https://...",
  "scraped_at": "2026-04-15T08:00:00Z"
}
```

**Detail:** Full listing object including score_breakdown, infrastructure_distances, coordinates, structured_analysis, etc.

## Module Design

### Module: `GET /api/listings/top`
- **Responsibility:** Query MongoDB for top-scored available listings from last 7 days
- **Interface:** Query params (limit, min_score, buyer_profile, district) → JSON array
- **Dependencies:** MongoDB via `mongodb_handler`
- **Size target:** ~30 lines

### Module: `GET /api/listings/[id]`
- **Responsibility:** Fetch single listing by MongoDB ObjectId
- **Interface:** Path param `id` → full listing JSON
- **Dependencies:** MongoDB via `mongodb_handler`
- **Size target:** ~20 lines

### Module: `POST /api/listings/[id]/check`
- **Responsibility:** HTTP HEAD request to listing URL, update url_is_valid in MongoDB
- **Interface:** Path param `id` → `{ "url_is_valid": true/false }`
- **Dependencies:** MongoDB, `requests` library
- **Size target:** ~25 lines

### Module: Dashboard List View
- **Responsibility:** Display filtered, sortable listing cards
- **Interface:** Fetches from `/api/listings/top`, renders grid
- **Dependencies:** Next.js, Tailwind CSS
- **Size target:** ~100 lines component

### Module: Listing Detail View
- **Responsibility:** Full listing display with actions
- **Interface:** Props: listing object, onRecheck callback
- **Dependencies:** Next.js, Tailwind CSS
- **Size target:** ~150 lines component

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | Connection string to existing MongoDB |

## Anti-Goals (Out of Scope)

- Authentication / user management
- Multiple user support
- Email / Telegram sending from dashboard
- Write operations to listings
- Data export
