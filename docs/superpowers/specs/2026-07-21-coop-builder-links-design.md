---
title: /coop — Genossenschaft rentals only, links to builder reservation page
date: 2026-07-21
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# /coop: Genossenschaft rentals only + builder-direct reservation links

## Problem (from user, verified in code)

The live `/coop` page showed:

1. **For-sale apartments** (Eigentum) mixed in with co-op rentals.
2. Listing links pointing to **Willhaben**, not the builder's own site where a unit
   can actually be reserved.

### Root cause (verified)

- `field_extractors.extract_is_genossenschaft()` tags **any** Willhaben listing whose
  full text mentions co-op markers (`genossenschaft`, `gefördert`, `finanzierungsbeitrag`,
  `eigenmittelanteil`, `mietkauf`, …). It has **no rent-vs-buy gate**, so a for-sale
  Eigentum flat that merely mentions those words gets `is_genossenschaft=True`,
  `coop_source="willhaben"`, and keeps its **Willhaben URL**.
- `dashboard/app/coop/page.tsx` query is `{ is_genossenschaft: true, url_is_valid: {$ne:false} }`
  — no `coop_source` filter, so those Willhaben rows render, linking to Willhaben.
- Legit **mygewo** units store the aggregator URL (`mygewo.at/angebot/…`), not the builder.

### Feasibility findings (verified live)

- mygewo aggregates **builder** sites (wohnen.at, arwag.at, gesiba.at, oevw.at,
  siedlungsunion.at) — **never Willhaben**. So "even if found on Willhaben, go to the
  builder" is solved simply by dropping Willhaben-sourced rows.
- The mygewo detail page (TanStack Start SSR) contains an **"Original-Anzeige"** anchor
  linking to the builder's exact reservation page. A full `requests.get` (gzip/chunked,
  ~43 KB) returns it — **no headless browser needed**. `bs4.find('a', string=…)` fails
  (nested markup); a `get_text()` scan over `<a href>` works.
- JSON-LD `provider.name` gives the builder name (homepage-fallback source).

## Design decisions (user-approved)

1. **`/coop` shows builder-direct co-ops only** — drop all `coop_source="willhaben"` rows.
   Kills the for-sale leak AND the Willhaben links at once. Cross-source-deduped units are
   already flipped to `bautraeger_direct` (main.py:475) so genuine matched units survive.
   Trade-off accepted: pure-Willhaben-only co-ops (no builder equivalent) are not shown.
2. **mygewo units resolve to the builder's deep-link** via the "Original-Anzeige" anchor;
   fall back to the builder homepage (from JSON-LD / "gefunden auf X.at") if unresolved.

## Modules

### Module: resolve_builder_url (genossenschaft_scraper.py)
- **Responsibility:** Given a mygewo `/angebot/` URL, return the builder's exact
  reservation URL (the "Original-Anzeige" href), or a builder homepage fallback, or None.
- **Interface:** `resolve_builder_url(offer_url: str) -> Optional[str]`. Fetches the detail
  page with the module's existing `fetch()`; parses with BeautifulSoup.
- **Dependencies:** `requests`, `bs4` (already imported).
- **Size target:** ~30 lines.

### Module: builder_url enrichment (run_coop.py)
- **Responsibility:** For each newly-seen mygewo unit lacking a stored `builder_url`,
  resolve it once and attach it before upsert.
- **Interface:** inline in `run()` seen-loop; skips units whose existing DB doc already
  has `builder_url` (bounded to genuinely new offers — the search page is conditional-GET).
- **Dependencies:** `resolve_builder_url`, `MongoDBHandler.get_listing`.
- **Size target:** ~10 lines.

### Module: /coop query + link (dashboard/app/coop/page.tsx)
- **Responsibility:** Query builder-direct co-ops only; link each row to its builder URL.
- **Interface:** Mongo filter adds `coop_source: { $ne: 'willhaben' }`; projection adds
  `builder_url`; `CoopRow` gains `builder_url`; `href = r.builder_url ?? r.url`.
- **Dependencies:** none new.
- **Size target:** existing file, ~6 changed lines.

### Module: Domain + Telegram consistency
- **Responsibility:** Persist and surface `builder_url` consistently.
- **Interface:** `Domain/listing.py` adds `builder_url: Optional[str] = None`.
  `main.py` coop broadcast candidate filter adds `and listing.coop_source != 'willhaben'`.
  `coop_format.format_coop_message` link uses `l.builder_url or l.url`.
- **Size target:** 3 one-line edits.

## Data flow

```
run_coop poll (mygewo search, conditional GET)
  → parse_mygewo (url = mygewo/angebot, coop_source=bautraeger_direct)
  → for new units: resolve_builder_url(url) → listing.builder_url
  → upsert_coop_listing (stores url + builder_url)
/coop page: find({is_genossenschaft, coop_source != willhaben}) → href = builder_url ?? url
```

`url` stays the mygewo URL (stable dedup/upsert key); `builder_url` is a separate field —
no dedup churn if resolution intermittently fails.

## Edge cases

- Multiple `.at` deep-links on a mygewo page (similar-offers cards) → match the
  **"Original-Anzeige"** anchor specifically, not the first external link.
- Resolution network failure → `builder_url` stays None → page/Telegram fall back to `url`.
- Kaufoption units are *gefördert rentals with a buy option* (still reservable rentals) —
  kept; existing `Kaufoption` badge already flags them.
- Direct adapters (ÖVW/FWB/BWSG) already store builder URLs → `builder_url` optional there;
  page falls back to `url` (already builder-direct).

## Testing (test_scope: true, ui_scope: true)

- **Unit:** `resolve_builder_url` extracts the Original-Anzeige href from a saved fixture,
  returns None when the anchor is absent; `_to_doc`/upsert round-trips `builder_url`.
- **Query:** a Willhaben-sourced (`coop_source="willhaben"`) row is excluded from `/coop`.
- **Playwright (per .claude/rules/ui-testing.md):** `/coop` list item `href` domain is
  **not** willhaben.at and **not** mygewo.at (asserts on real DOM, per-cycle).

## Not doing

- Willhaben→builder deep-resolution (moot — Willhaben dropped from co-op surfaces).
- Removing the Willhaben co-op *tag* (kept — powers cross-source dedup that upgrades matched
  units to builder URLs).
