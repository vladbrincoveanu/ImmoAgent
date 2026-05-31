# Login Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify auth to a working, simple login with custom session cookie.

**Architecture:** Login page submits to `/api/auth/login` → validates credentials → sets `immo_session` cookie. Middleware checks cookie on `/dashboard/*`. No NextAuth complexity.

**Tech Stack:** Next.js App Router, native fetch, httpOnly cookies.

---

## File Structure

- Modify: `app/api/auth/login/route.ts` - handle POST with JSON body, set cookie
- Modify: `app/(auth)/login/page.tsx` - use JSON fetch instead of form redirect
- Modify: `lib/auth.ts` - simplify to session decode utility
- Modify: `middleware.ts` - already correct, no changes needed

---

### Task 1: Simplify login API route

**Files:**
- Modify: `app/api/auth/login/route.ts`

- [ ] **Step 1: Rewrite API route**

```typescript
import { NextResponse } from 'next/server'

const ADMIN_USER = process.env.ADMIN_USER || 'admin'
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'password'
const SESSION_COOKIE = 'immo_session'

function createSessionToken(user: string): string {
  const payload = `${user}:${Date.now()}`
  return Buffer.from(payload).toString('base64')
}

export async function POST(request: Request) {
  const body = await request.json()
  const { username, password } = body

  if (!username || !password) {
    return NextResponse.json({ error: 'Missing credentials' }, { status: 400 })
  }

  if (username !== ADMIN_USER || password !== ADMIN_PASSWORD) {
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
  }

  const token = createSessionToken(username)
  const response = NextResponse.json({ success: true })
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30,
    path: '/',
  })

  return response
}

export async function GET() {
  return NextResponse.json({ error: 'Method not allowed' }, { status: 405 })
}
```

- [ ] **Step 2: Commit**

```bash
git add app/api/auth/login/route.ts
git commit -m "refactor: simplify login API to JSON response + cookie"
```

---

### Task 2: Update login page to use JSON fetch

**Files:**
- Modify: `app/(auth)/login/page.tsx`

- [ ] **Step 1: Rewrite login page**

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    if (res.ok) {
      router.push('/dashboard')
      router.refresh()
    } else {
      const data = await res.json()
      setError(data.error || 'Login failed')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow">
        <h2 className="text-center text-2xl font-bold mb-6">Immo-Scouter</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-red-500 text-sm text-center">{error}</div>
          )}
          <div>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded border p-2"
              required
            />
          </div>
          <div>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border p-2"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add app/\(auth\)/login/page.tsx
git commit -m "refactor: login page uses JSON fetch, cleaner UI"
```

---

### Task 3: Simplify auth utility

**Files:**
- Modify: `lib/auth.ts`

- [ ] **Step 1: Rewrite auth utility**

```typescript
export function decodeSession(cookieValue: string): { user: string } | null {
  try {
    const decoded = Buffer.from(cookieValue, 'base64').toString('utf-8')
    const [user] = decoded.split(':')
    return user ? { user } : null
  } catch {
    return null
  }
}

export function validateSession(cookieValue: string | undefined): boolean {
  if (!cookieValue) return false
  return decodeSession(cookieValue) !== null
}
```

- [ ] **Step 2: Commit**

```bash
git add lib/auth.ts
git commit -m "refactor: simplify auth.ts to session decode utility"
```

---

### Task 4: Test login flow

- [ ] **Step 1: Start dev server and test**

```bash
cd dashboard && npm run dev &
sleep 5
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}' \
  -v
```

Expected: 200 OK with `Set-Cookie: immo_session=...`

- [ ] **Step 2: Test dashboard access with cookie**

```bash
curl -b "immo_session=<token>" http://localhost:3000/dashboard -I
```

Expected: 200 OK (no redirect)

- [ ] **Step 3: Test dashboard without cookie**

```bash
curl http://localhost:3000/dashboard -I
```

Expected: 302 redirect to /login

- [ ] **Step 4: Stop dev server**

```bash
pkill -f "next dev"
```

---

### Task 5: Add environment variables

**Files:**
- Modify: `.env.local.example`

- [ ] **Step 1: Add auth env vars**

```
ADMIN_USER=admin
ADMIN_PASSWORD=password
```

- [ ] **Step 2: Commit**

```bash
git add .env.local.example
git commit -m "docs: add ADMIN_USER and ADMIN_PASSWORD to env example"
```