---
title: Freemium gate for buyer flow (soft gate, no auth)
date: 2026-07-04
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Freemium Buyer Gate — Design

## Goal
Turn the aspirational Free/Pro split on the landing page into real, server-enforced gating — without auth or payment infra. Path C: cookie-identified anon users, email capture at the paywall, manual Pro flip in Mongo. Renter features explicitly out of scope (V3).

## Free vs Pro boundary (matches landing page `app/page.tsx` promises)

| Feature | Free | Pro |
|---|---|---|
| Browse listings, map, heatmap, filters, mortgage calc | ✅ | ✅ |
| All 8 buyer profiles | ✅ | ✅ |
| Saved searches | 3 | Unlimited |
| Email alerts | ❌ | ✅ |

Landing page already promises exactly this; no landing copy changes needed.

## Identity & entitlement
- Identity: existing `immo_user` cookie (`u_<24hex>`), 1-year maxAge. No login.
- Entitlement: Mongo collection `users`: `{_id: <user_id>, email?, is_pro: boolean, created_at}`. Absent doc = free.
- Pro flip (manual, until Stripe): `db.users.updateOne({_id:'u_...'},{$set:{is_pro:true}},{upsert:true})`.
- Known limitation (accepted): cookie clearing resets the free quota. Fine for v1 — the goal is upgrade-intent capture, not fraud prevention.

## Modules

### Module: `dashboard/lib/user.ts`
- **Responsibility:** Single source for anon-user identity + entitlements (extracts the `getOrCreateUserId` currently duplicated in 2 routes).
- **Interface:** `COOKIE_NAME`, `getOrCreateUserId(req)`, `setUserCookie(res, userId)`, `isPro(db, userId): Promise<boolean>`, `FREE_SAVED_SEARCH_LIMIT = 3`.
- **Dependencies:** `mongodb.ts` Db type, next/server.
- **Size target:** <60 lines.

### Module: `app/api/saved-searches/route.ts` (modify POST)
- **Responsibility:** Enforce free limit: if `!isPro` and count ≥ 3 → HTTP 402 `{error:'upgrade_required', reason:'saved_search_limit', limit:3}`.
- **Dependencies:** lib/user.ts.

### Module: `app/api/saved-searches/alert/route.ts` (modify POST)
- **Responsibility:** Alerts Pro-only: if `!isPro` → HTTP 402 `{error:'upgrade_required', reason:'alerts_pro_only'}`. Pro users keep existing double opt-in flow unchanged.
- **Dependencies:** lib/user.ts.

### Module: `app/api/me/route.ts` (new)
- **Responsibility:** GET → `{is_pro, saved_search_count, saved_search_limit}` for UI state (badge, pre-emptive gating).
- **Dependencies:** lib/user.ts, mongodb.
- **Size target:** <40 lines.

### Module: `app/api/upgrade/route.ts` (new)
- **Responsibility:** POST `{email, reason}` → upsert lead into `upgrade_requests` `{user_id, email, reason, created_at}` (one doc per user_id+email). Returns `{ok:true}`. This is the paywall email capture; owner reviews and flips `is_pro` manually.
- **Dependencies:** lib/user.ts, mongodb.
- **Size target:** <50 lines.

### Module: `components/PaywallModal.tsx` (new)
- **Responsibility:** Upgrade prompt shown on 402. Copy varies by reason (saved-search limit vs alerts). Email input → POST /api/upgrade → success state ("You're on the early-access list"). testids: `paywall-modal`, `paywall-email`, `paywall-submit`, `paywall-success`.
- **Dependencies:** none beyond React.
- **Size target:** <120 lines.

### Module: UI wiring (modify)
- `SaveSearchButton.tsx`: on POST 402 → open PaywallModal (reason `saved_search_limit`).
- `EmailAlertsModal.tsx`: on POST 402 → swap form body to inline upgrade state — reuse entered email, one-click "Request Pro access" → POST /api/upgrade.

## Error handling
- 402 chosen (Payment Required) — unambiguous vs 403, easy to branch on client.
- DB unavailable → existing 503 paths unchanged; gate fails closed for alerts (no isPro proof → treated free), fails open only if the count query errors (then existing 500 path).

## Testing (`dashboard/tests/freemium-gate.spec.ts`)
1. Fresh context: create 3 saved searches via API → all 201; 4th → 402 with `reason: saved_search_limit`.
2. UI: with 3 saves present, click Save search → PaywallModal visible (DOM testid, not screenshot).
3. Alert subscribe as free user → 402; EmailAlertsModal shows upgrade state; submitting email → /api/upgrade 200 and success testid visible.
4. /api/me returns `is_pro:false`, correct count/limit.
Full Playwright suite as final gate.

## Out of scope
Stripe/payments, real auth, renter pipeline, alert-sending cron, quota-evasion hardening.
