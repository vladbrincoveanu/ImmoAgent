# Plan 6 of 6: Dashboard Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add login UI for auth, listing detail page, real-time updates (SSE), filter persistence in URL, mobile map improvements, dark mode.

**Architecture:** NextAuth.js for authentication. Server-Sent Events for real-time data. URL query params for filter state. Zustand or React context for client state. Bottom sheet pattern for mobile map. next-themes for dark mode.

**Tech Stack:** Next.js 14, NextAuth.js, react-leaflet, zustand, next-themes, SWR or fetch with revalidate

---

## File Map

```
dashboard/
  app/
    (auth)/
      login/page.tsx              # Create: login page
    dashboard/
      listings/[id]/page.tsx      # Create: listing detail page
      page.tsx                    # Modify: filter persistence in URL, Zustand state
      layout.tsx                  # Modify: add NextAuth session provider
      map/page.tsx                # Modify: mobile bottom sheet, real-time updates
  components/
    FilterBar.tsx                 # Modify: sync filters to URL params
    ListingCard.tsx                # Modify: add click to detail page
    MapView.tsx                    # Modify: real-time SSE updates
    BottomSheet.tsx               # Create/Modify: mobile bottom sheet
  lib/
    auth.ts                        # Create: NextAuth config
    sse.ts                         # Create: SSE client hook
    filters.ts                     # Create: URL filter state utilities
  package.json                    # Modify: add next-auth, zustand, next-themes, swr
  middleware.ts                   # Create: auth protection middleware
```

---

## Task 1: Add NextAuth.js authentication (login page + session)

**Files:**
- Modify: `dashboard/package.json`, `dashboard/app/layout.tsx`, `dashboard/app/(auth)/login/page.tsx`, Create: `dashboard/lib/auth.ts`

- [ ] **Step 1: Install next-auth and zustand**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm install next-auth zustand swr
```

- [ ] **Step 2: Create NextAuth config in lib/auth.ts**

```typescript
import NextAuth from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

export default NextAuth({
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(credentials)
        })
        const user = await res.json()
        if (res.ok && user) return user
        return null
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.role = user.role
      return token
    },
    async session({ session, token }) {
      session.user.role = token.role
      return session
    }
  },
  pages: {
    signIn: '/login',
    error: '/login'
  }
})
```

- [ ] **Step 3: Update layout.tsx to wrap with SessionProvider**

```typescript
// In dashboard/app/layout.tsx
import { SessionProvider } from 'next-auth/react'
import { auth } from '@/lib/auth'

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  return (
    <html lang="en">
      <body>
        <SessionProvider session={session}>
          {children}
        </SessionProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 4: Create login page**

Create `dashboard/app/(auth)/login/page.tsx`:
```typescript
'use client'
import { signIn } from 'next-auth/react'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const result = await signIn('credentials', {
      username, password, redirect: false
    })
    if (result?.error) {
      setError('Invalid credentials')
    } else {
      router.push('/dashboard')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded shadow-md w-96">
        <h1 className="text-2xl font-bold mb-6">Immo-Scouter Login</h1>
        {error && <div className="text-red-500 mb-4">{error}</div>}
        <input
          type="text" placeholder="Username"
          value={username} onChange={e => setUsername(e.target.value)}
          className="w-full border p-2 rounded mb-4"
        />
        <input
          type="password" placeholder="Password"
          value={password} onChange={e => setPassword(e.target.value)}
          className="w-full border p-2 rounded mb-6"
        />
        <button type="submit" className="w-full bg-blue-600 text-white p-2 rounded">
          Sign In
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 5: Create auth API route**

Create `dashboard/app/api/auth/[...nextauth]/route.ts`:
```typescript
import NextAuth from 'next-auth'
import { auth } from '@/lib/auth'

const handler = NextAuth(auth)
export { handler as GET, handler as POST }
```

- [ ] **Step 6: Add middleware for protected routes**

Create `dashboard/middleware.ts`:
```typescript
export { default } from 'next-auth/middleware'

export const config = {
  matcher: ['/dashboard/:path*', '/api/listings/:path*']
}
```

- [ ] **Step 7: Commit**
```bash
git add dashboard/package.json dashboard/app/layout.tsx dashboard/app/\(auth\)/login/page.tsx dashboard/lib/auth.ts dashboard/app/api/auth/\[...nextauth\]/route.ts dashboard/middleware.ts
git commit -m "feat: add NextAuth.js login page and session management"
```

---

## Task 2: Create listing detail page

**Files:**
- Create: `dashboard/app/dashboard/listings/[id]/page.tsx`, Modify: `dashboard/components/ListingCard.tsx`, `dashboard/app/api/listings/[id]/route.ts`

- [ ] **Step 1: Read ListingCard.tsx to understand current structure**

Find how listings are displayed and where the URL comes from.

- [ ] **Step 2: Add click handler to navigate to detail page**

```typescript
// In ListingCard.tsx, add onClick:
'use client'
import { useRouter } from 'next/navigation'
const router = useRouter()

<div onClick={() => router.push(`/dashboard/listings/${listing._id}`)} className="cursor-pointer">
```

- [ ] **Step 3: Create listing detail page**

Create `dashboard/app/dashboard/listings/[id]/page.tsx`:
```typescript
import { getDb } from '@/lib/mongodb'
import { notFound } from 'next/navigation'

interface Props {
  params: { id: string }
}

export default async function ListingDetailPage({ params }: Props) {
  const db = await getDb()
  const listing = await db.collection('listings').findOne({ _id: params.id })

  if (!listing) notFound()

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold mb-2">{listing.title}</h1>
        <p className="text-gray-600 mb-4">{listing.address}</p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div><strong>Price:</strong> €{listing.price_total?.toLocaleString()}</div>
          <div><strong>Area:</strong> {listing.area_m2}m²</div>
          <div><strong>Rooms:</strong> {listing.rooms}</div>
          <div><strong>Bezirk:</strong> {listing.bezirk}</div>
          <div><strong>Score:</strong> <span className="text-green-600">{listing.score}/100</span></div>
          <div><strong>Energy Class:</strong> {listing.energy_class || 'N/A'}</div>
        </div>

        {listing.score_breakdown && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-2">Score Breakdown</h2>
            <div className="space-y-1">
              {Object.entries(listing.score_breakdown).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span>{key.replace('_', ' ')}</span>
                  <span>{value}/100</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-4">
          <a href={listing.url} target="_blank" rel="noopener noreferrer"
             className="bg-blue-600 text-white px-4 py-2 rounded">
            View on {listing.source}
          </a>
          <a href={`/dashboard`} className="bg-gray-200 px-4 py-2 rounded">
            Back to Dashboard
          </a>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**
```bash
git add dashboard/app/dashboard/listings/[id]/page.tsx dashboard/components/ListingCard.tsx
git commit -m "feat: add listing detail page with score breakdown"
```

---

## Task 3: Persist filter state in URL query params

**Files:**
- Modify: `dashboard/components/FilterBar.tsx`, `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Create URL filter utilities**

Create `dashboard/lib/filters.ts`:
```typescript
export function filtersToParams(filters: Record<string, string | string[] | number | undefined>) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => params.append(key, v))
      } else {
        params.set(key, String(value))
      }
    }
  })
  return params.toString()
}

export function paramsToFilters(searchParams: URLSearchParams): Record<string, string> {
  const filters: Record<string, string> = {}
  searchParams.forEach((value, key) => {
    filters[key] = value
  })
  return filters
}
```

- [ ] **Step 2: Modify FilterBar to sync to URL**

In `FilterBar.tsx`, add:
```typescript
'use client'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect } from 'react'

export function FilterBar() {
  const router = useRouter()
  const searchParams = useSearchParams()

  // Update URL when filter changes
  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set(key, value)
    else params.delete(key)
    router.push(`/dashboard?${params.toString()}`)
  }

  // Clear all filters
  const clearFilters = () => {
    router.push('/dashboard')
  }

  // Read initial filters from URL
  const activeFilters = paramsToFilters(searchParams)

  return (
    <div className="flex gap-2 flex-wrap">
      {/* district filter */}
      <select onChange={e => updateFilter('bezirk', e.target.value)}
              value={activeFilters.bezirk || ''}>
        <option value="">All Districts</option>
        {/* districts 1010-1230 */}
      </select>
      {/* price range */}
      <input type="number" placeholder="Min Price"
             onChange={e => updateFilter('price_min', e.target.value)}
             value={activeFilters.price_min || ''} />
      {/* ... other filters ... */}
      <button onClick={clearFilters} className="text-gray-500 text-sm">
        Clear Filters
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Read filters from URL in dashboard page**

In `dashboard/app/dashboard/page.tsx`:
```typescript
import { paramsToFilters } from '@/lib/filters'

export default function DashboardPage({ searchParams }: { searchParams: URLSearchParams }) {
  const filters = paramsToFilters(searchParams)
  const { data: listings, isLoading } = useSWR(
    `/api/listings?${searchParams.toString()}`
  )
  // ...
}
```

- [ ] **Step 4: Commit**
```bash
git add dashboard/lib/filters.ts dashboard/components/FilterBar.tsx dashboard/app/dashboard/page.tsx
git commit -m "feat: persist filter state in URL query params"
```

---

## Task 4: Add real-time updates via Server-Sent Events (SSE)

**Files:**
- Create: `dashboard/app/api/listings/stream/route.ts`, `dashboard/lib/sse.ts`, Modify: `dashboard/components/MapView.tsx`

- [ ] **Step 1: Create SSE API route**

Create `dashboard/app/api/listings/stream/route.ts`:
```typescript
import { getDb } from '@/lib/mongodb'

export async function GET() {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      const db = await getDb()
      const pipeline = [
        { $match: { operationType: 'insert' } },
        { $limit: 10 }
      ]
      const changeStream = db.collection('listings').watch(pipeline)

      changeStream.on('change', (change) => {
        const data = JSON.stringify({ type: 'new_listing', data: change.fullDocument })
        controller.enqueue(encoder.encode(`data: ${data}\n\n`))
      })

      // Send heartbeat every 30s
      const heartbeat = setInterval(() => {
        controller.enqueue(encoder.encode(`: heartbeat\n\n`))
      }, 30000)

      // Cleanup on close
      return () => {
        clearInterval(heartbeat)
        changeStream.close()
      }
    }
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  })
}
```

- [ ] **Step 2: Create useSSE hook**

Create `dashboard/lib/sse.ts`:
```typescript
import { useEffect, useState } from 'react'

export function useListingsSSE() {
  const [listings, setListings] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const eventSource = new EventSource('/api/listings/stream')

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        if (parsed.type === 'new_listing') {
          setListings(prev => [parsed.data, ...prev])
        }
      } catch {
        // Ignore parse errors
      }
    }

    eventSource.onerror = () => {
      setError('SSE connection lost')
    }

    return () => eventSource.close()
  }, [])

  return { listings, error }
}
```

- [ ] **Step 3: Use in map view**

In `MapView.tsx`:
```typescript
const { listings: newListings } = useListingsSSE()
useEffect(() => {
  if (newListings.length > 0) {
    setListings(prev => [...newListings, ...prev])
  }
}, [newListings])
```

- [ ] **Step 4: Commit**
```bash
git add dashboard/app/api/listings/stream/route.ts dashboard/lib/sse.ts dashboard/components/MapView.tsx
git commit -m "feat: add real-time listing updates via Server-Sent Events"
```

---

## Task 5: Fix mobile responsive map (bottom sheet pattern)

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`, `dashboard/components/BottomSheet.tsx`, `dashboard/components/MapView.tsx`

- [ ] **Step 1: Read BottomSheet.tsx**

Check what's already there.

- [ ] **Step 2: Update map page for mobile bottom sheet**

```typescript
// In map/page.tsx
'use client'
import { useState } from 'react'

export default function MapPage() {
  const [selectedListing, setSelectedListing] = useState(null)
  const [isBottomSheetOpen, setIsBottomSheetOpen] = useState(false)

  return (
    <div className="h-screen flex flex-col">
      {/* Map fills screen */}
      <div className="flex-1 relative">
        <MapView
          onListingClick={(listing) => {
            setSelectedListing(listing)
            setIsBottomSheetOpen(true)
          }}
        />
      </div>

      {/* Mobile bottom sheet */}
      {isBottomSheetOpen && selectedListing && (
        <BottomSheet onClose={() => setIsBottomSheetOpen(false)}>
          <ListingCard listing={selectedListing} expanded />
        </BottomSheet>
      )}

      {/* Desktop sidebar */}
      <div className="hidden md:block w-80 bg-white overflow-y-auto border-l">
        <Sidebar listings={listings} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Implement BottomSheet component**

Ensure `BottomSheet.tsx` uses CSS transform for smooth sliding:
```typescript
export function BottomSheet({ children, onClose }: { children: React.ReactNode, onClose: () => void }) {
  return (
    <div className="fixed inset-x-0 bottom-0 bg-white rounded-t-2xl shadow-2xl z-50 max-h-[70vh] overflow-y-auto">
      <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mt-3 mb-4" />
      <button onClick={onClose} className="absolute top-2 right-2 p-2">✕</button>
      {children}
    </div>
  )
}
```

- [ ] **Step 4: Commit**
```bash
git add dashboard/app/dashboard/map/page.tsx dashboard/components/BottomSheet.tsx
git commit -m "fix: implement mobile bottom sheet for map listing selection"
```

---

## Task 6: Add dark mode support via next-themes

**Files:**
- Modify: `dashboard/package.json`, `dashboard/app/layout.tsx`, `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Install next-themes**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm install next-themes
```

- [ ] **Step 2: Add ThemeProvider and toggle**

In `layout.tsx`:
```typescript
import { ThemeProvider } from 'next-themes'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 3: Add theme toggle button**

In the dashboard header/nav:
```typescript
'use client'
import { useTheme } from 'next-themes'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 rounded bg-gray-200 dark:bg-gray-700">
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
```

- [ ] **Step 4: Add dark mode CSS to tailwind.config.js**

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  // ...
}
```

- [ ] **Step 5: Commit**
```bash
git add dashboard/package.json dashboard/app/layout.tsx
git commit -m "feat: add dark mode support via next-themes"
```

---

## Verification

1. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm run build` — must succeed
2. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx playwright test tests/smoke.spec.ts --reporter=list` — must pass
3. Manual: Visit `/login` page, verify login form renders
4. Manual: Navigate to map page, resize to mobile — bottom sheet should appear

---

## Plan 6 Self-Review

| Spec Item | Covered? | Task |
|---|---|---|
| No user auth (login UI) | ✅ | Task 1 |
| No listing detail page | ✅ | Task 2 |
| Filter state not persisted | ✅ | Task 3 |
| No real-time updates | ✅ | Task 4 |
| Mobile responsive map | ✅ | Task 5 |
| No dark mode | ✅ | Task 6 |