---
title: Co-op full builder coverage, unit identity, and filter UX
date: 2026-07-28
status: draft
ui_scope: true
graph_scope: false
test_scope: true
---

# Co-op full builder coverage, unit identity, and filter UX

## Problem

`/coop` renders **17 units from 8 builders**. Two independent problems produce that number.

### Problem 1 — unit identity collapse (the dominant loss)

mygewo's Wien search reports **65 units**; the scraper's own docstring records 75 units / 58 rentals at time of writing. We render 17. The loss is not in the dashboard query — it is in unit identity, and it happens twice.

**1a. The cross-source fingerprint over-collapses within a single source.**

`Project/Application/helpers/listing_validator.py:96-107`:

```
compute_xsrc_fingerprint = md5( norm(bautraeger) | norm(address) | round(area) | rooms )
```

No unit identifier, no floor, no price. And mygewo addresses are street-level only —
`genossenschaft_scraper.py:363-365` builds `f"{street}, {zipcode} Wien"`, never a Top or Stiege.

A Genossenschaft new-build is the pathological case: 8 apartments at one address, one builder, all "3 Zimmer / 68 m²" produce **8 identical fingerprints**. `upsert_coop_listing` returns `"duplicate"` for 7 of them, logged at `info`. The units are silently discarded.

The fingerprint was designed to bridge *two sources describing one unit*. It is being applied *within one source*, where distinct apartments legitimately share every field in the key.

**1b. Units from RPC pages 1+ share a Mongo key.**

`genossenschaft_scraper.py:354`:

```python
url = uuid_to_offer.get(u["uuid"] or "", builder_url)
```

`uuid_to_offer` is built from server-rendered cards, which mygewo emits for **page 0 only** (~25 units — documented at `genossenschaft_scraper.py:313-317`). Every unit from RPC page 1 onward falls back to `builder_url`: the builder's *project* reservation page, shared by every unit in that project. `upsert_coop_listing` keys on `url`, so those units **overwrite one another**.

Both bugs are silent and compounding. mygewo supplies `uuid` and `external_unit_id` per unit (`genossenschaft_scraper.py:265`, `:255`); we parse `uuid` and use it only for URL lookup. The identity we need is already in hand, unused.

**Explicitly ruled out.** An earlier hypothesis blamed the dashboard's `BASE_QUERY`
(`dashboard/app/coop/page.tsx:45-54`) for requiring `bezirk: /^1\d{3}$/` and `buyable: false`. Reading the scraper disproves it: line 350 already drops any unit whose zipcode fails `^1\d{3}$`, and line 357 hard-stamps `listing.buyable = False` on every emitted unit. For mygewo-sourced rows both clauses are **no-ops**. They stay as defense-in-depth for future adapters. Likewise the `1101` value in the live district dropdown is a genuine Vienna PLZ returned by mygewo, not a parsing defect.

### Problem 2 — source coverage

`genossenschaft_scraper.py:52-64` defines exactly one live source. The ÖVW, Familienwohnbau and BWSG adapters are **commented out** as "redundant with mygewo".

The GBV Bauträgerliste for Wien (Stand 01.10.2022) lists ~70 entries collapsing to **~45 distinct parent organisations**. mygewo carries roughly 10. Never crawled: SOZIALBAU AG (the largest, trading under 6 further brands), BUWOG, WBV-GPA, Wien-Süd/Merkur, Heimbau/Eisenhof, Migra, EBG, GSG, Schwarzatal, Mischek/Daheim/Wiener Heim, Süd-Ost, EBSG, Wohnpark Alt Erlaa, Kabelwerk, Kallco, Heimat Österreich, and ~20 more.

The list is alias-dense. Naive per-name crawling double-counts:

| Parent | Brands in the GBV list |
|---|---|
| SOZIALBAU AG | Familie, Neuland, Urbanbau, Vindobona, Volksbau, Wohnbau |
| ÖVW | Patria, Wiener |
| Mischek | Daheim, Mischek Leasing eins, Wiener Heim |
| GESIBA | STEG, Wohnpark Alt Erlaa |
| ARWAG | WEVAG, Fonds für temporäres Wohnen |
| ÖSW | Krottenbach, Wohnungseigentum |
| Wien-Süd | Merkur |
| Heimbau | Eisenhof |

### Problem 3 — builder filter UX

`dashboard/app/coop/page.tsx:313-320` renders a single-select `<select>` with one `<option>` per distinct `bautraeger`. Tolerable at 8 builders; unusable at 45. Single-select also prevents the common query "show me SOZIALBAU **and** GESIBA".

## Decisions taken

Recorded because several were contested during design and the rationale must survive.

| Decision | Choice | Note |
|---|---|---|
| Crawl strategy | Bespoke adapter per builder, all ~45 | User's explicit call, reaffirmed after the maintenance-cost objection was raised. Mitigated by a shared base class confining each adapter to selectors, plus health alarms. |
| Dedup fix | Strengthen the fingerprint fields | User's call over the two-tier alternative. Carries a real risk (below) that is gated by a fail-loud test, not assumed away. |
| Unit identity | New `coop_uid` field, upserts key on it | |
| Poll cadence | Tiered + bounded parallel fetch pool | |
| Builder filter | Searchable multi-select chips with counts | |
| NÖ-only orgs | In registry, `wien_active: false`, not crawled | Alpenland (St. Pölten), Geboes (Trumau), Familienwohnbau NÖ. Flip the flag if they list Wien objects. |
| mygewo-covered builders | Still get adapters, crawled **last** | Least marginal value, most dedup pressure. |
| Registry storage | One JSON consumed by Python and TypeScript | No duplicated builder list. |

**Known risk, accepted and instrumented.** Strengthening the fingerprint with floor/Top and price weakens exactly what the weak key was for: Willhaben rarely publishes Top/Stiege and rounds prices differently, so Willhaben↔Bauträger pairs may stop collapsing and resurface as duplicates on the map, in Telegram, and in top-5. Mitigation is a regression test over real fixture pairs that **fails the build** if a known pair stops collapsing (Module 2, Testing). If that test cannot be made to pass, the two-tier design is the fallback and this decision gets revisited — it is not silently absorbed.

## Success criteria

Measured, not asserted.

1. **Identity fix alone** raises `/coop` from 17 to **≥40** units with zero new adapters. Verified by the funnel report before and after.
2. Every ~45 GBV Wien parent org is present in the registry; every `wien_active` org is either crawled by an adapter or explicitly marked `covered_by_mygewo`.
3. No unit appears twice under two brand names of one parent.
4. A broken adapter raises a Telegram alert within one poll cycle of dropping non-zero → zero.
5. Builder filter supports multi-select over 45 builders with per-builder counts, verified by Playwright DOM assertions.
6. Full Playwright suite green; new behaviour covered by new tests.

## Architecture

```
Project/data/coop_builders.json        ← single registry, read by Python AND dashboard
Project/Application/scraping/coop/
    registry.py                        ← loads + validates the JSON, alias→parent resolution
    base.py                            ← CoopAdapter ABC + shared field parsing
    identity.py                        ← coop_uid construction
    health.py                          ← per-adapter run stats, breakage alarm
    pool.py                            ← tiered scheduling + bounded parallel fetch
    adapters/<slug>.py                 ← ~45 files, selectors only
Project/scripts/measure_coop_coverage.py  ← extended into a stage-by-stage funnel
dashboard/lib/coopBuilders.ts          ← reads the same JSON, parent rollup for the UI
dashboard/components/BuilderFilter.tsx ← searchable multi-select chips
```

Data flow unchanged in shape: `adapters → run_coop.py → upsert_coop_listing → MongoDB → /coop`. This spec changes what identifies a unit inside that flow, how many adapters feed it, and how the result is filtered.

---

## Module: registry

- **Responsibility:** Load and validate `coop_builders.json`; resolve any brand alias to its canonical parent.
- **Interface:** `all_builders() -> list[Builder]`, `wien_active() -> list[Builder]`, `resolve_parent(name: str) -> str`, `by_slug(slug: str) -> Builder`. `Builder` carries `slug, canonical_name, parent_slug, aliases, domain, offer_url, wien_active, covered_by_mygewo, poll_tier`.
- **Dependencies:** `Project/data/coop_builders.json` only. No network, no DB.
- **Size target:** ≤150 lines.

Validation runs at import and raises on: duplicate slug, alias pointing at an unknown parent, `wien_active` org with no `offer_url`. A malformed registry must fail loudly at startup, never degrade the crawl silently.

## Module: identity

- **Responsibility:** Produce the stable per-unit key and the strengthened dedup fingerprint.
- **Interface:** `coop_uid(source: str, unit_id: str) -> str` → `"{source}:{unit_id}"`. `strengthened_fingerprint(listing) -> str | None`.
- **Dependencies:** `listing_validator._norm`.
- **Size target:** ≤120 lines.

`coop_uid` uses mygewo's `external_unit_id`, falling back to `uuid`. Adapters for builders without a stable site-side id derive one from `sha1(slug | street | top | area | rooms | price)` — documented per adapter as derived, so a site redesign that shifts those fields is understood to churn ids.

The strengthened fingerprint extends the existing key with the fields that actually distinguish apartments:

```
md5( norm(bautraeger) | norm(address_incl_top) | round(area) | rooms | floor | price_bucket )
```

`price_bucket` rounds to the nearest €25 so that cross-source rounding differences do not split a genuine pair. `floor` and `top` are `""` when unknown, which is the degradation path the regression test guards.

A `coop_uid` unique partial index (`is_genossenschaft: true`) enforces identity at the database, not just in application code.

## Module: base (CoopAdapter)

- **Responsibility:** Define the adapter contract and implement every field-parsing concern once, so a per-builder adapter contains only selectors.
- **Interface:** ABC with `slug: str`, `offer_url: str`, `fetch() -> str`, `parse(html: str) -> list[RawUnit]`. Shared helpers: `parse_price`, `parse_area`, `parse_rooms`, `bezirk_from_address`, `classify_rent_vs_buy`, `detect_freiflaechen`, `to_listing`.
- **Dependencies:** `registry`, `identity`, `requests`, `BeautifulSoup`.
- **Size target:** ≤250 lines for the base; **≤120 lines per adapter**.

`classify_rent_vs_buy` is the highest-risk shared helper: mislabelling a Kauf unit as a rental leaks for-sale property onto a rentals-only page. It defaults to **buy** (i.e. drop) whenever the signal is ambiguous, so an unrecognised page shrinks the feed rather than corrupting it.

## Module: pool

- **Responsibility:** Schedule adapters by tier and fetch them through a bounded worker pool.
- **Interface:** `run_tier(tier: str, adapters: list[CoopAdapter]) -> list[AdapterResult]`.
- **Dependencies:** `concurrent.futures.ThreadPoolExecutor`, `health`.
- **Size target:** ≤150 lines.

Tiers: `fast` (mygewo, every 5 min, matching today) and `hourly` (all direct builder sites). Hourly adapters keep the existing conditional-GET change gate in `poll_source` — ~24 requests/site/day rather than 288.

Pool width caps at **8 concurrent fetches** with a per-domain limit of 1, so no single builder ever sees parallel requests from us. One adapter's failure or timeout (20 s, as today) must not abort the run; `run` already tolerates per-adapter exceptions and that contract is preserved.

## Module: health

- **Responsibility:** Record per-adapter outcomes and alert on breakage.
- **Interface:** `record(slug, unit_count, ok, error)`, `check_alarms() -> list[Alarm]`.
- **Dependencies:** `mongodb_handler` (a `coop_adapter_health` collection), `telegram_bot`.
- **Size target:** ≤150 lines.

Alarm conditions: non-zero → zero unit count; exception on two consecutive runs; no successful run in 24 h. Alerts go to the existing coop Telegram channel (`TELEGRAM_COOP_CHANNEL_ID`).

At 45 adapters this is what separates a maintainable system from silent rot. Without it the failure mode is precisely today's: a number that looks plausible and is quietly wrong.

## Module: funnel (measure_coop_coverage.py, extended)

- **Responsibility:** Count units at each pipeline stage, per builder, so loss is attributable rather than guessed at.
- **Interface:** CLI → stage table + `Project/log/coop_funnel_<date>.txt`.
- **Dependencies:** `mongodb_handler`, `registry`.
- **Size target:** ≤200 lines.

Stages: `parsed → rent-filtered → validated → upserted (inserted/updated/duplicate) → rendered`. The `duplicate` count per builder is the metric that would have surfaced Problem 1 immediately; it is the primary before/after evidence for success criterion 1.

This requires `upsert_coop_listing` — which already returns `"inserted" | "updated" | "duplicate" | "invalid" | "error"` — to have its return value **aggregated** by `run_coop.py` instead of discarded at `run_coop.py:186`.

## Module: BuilderFilter (dashboard)

- **Responsibility:** Searchable multi-select builder filter with counts and parent rollup.
- **Interface:** Props `{ builders: BuilderOption[], selected: string[] }`; emits repeated `bautraeger` query params. `BuilderOption = { slug, label, count, parentSlug }`.
- **Dependencies:** `dashboard/lib/coopBuilders.ts`.
- **Size target:** ≤200 lines.

Type-to-filter input, removable chips for selections, counts per option from one `$group` aggregation, zero-count builders rendered greyed and disabled rather than hidden — absence is itself information about coverage. Aliases roll up under their parent by default.

Server side, `buildQuery` (`dashboard/app/coop/page.tsx:69-91`) changes `f.bautraeger` from a scalar equality to `{ bautraeger: { $in: [...] } }`, expanding each selected parent to its brand aliases via the registry. This follows the file's existing `$and`-per-group convention; the empty-selection case must continue to mean "no constraint", not "match nothing".

---

## Error handling

- Malformed registry → raise at import. Loud.
- Adapter throws → logged, recorded in health, run continues. All adapters failing → exit 1 (existing behaviour, `run_coop.py:174-177`).
- Ambiguous rent/buy → treat as buy, drop the unit.
- Unknown builder name from an adapter → ingest under its raw name and record a health warning; never silently map to a wrong parent.
- `coop_uid` collision on genuinely distinct units → surfaced by the unique index as an upsert error, counted in the funnel.

## Testing

Per `.claude/rules/ui-testing.md` and the mandatory per-cycle DOM verification.

**Python**
- `identity`: distinct-units-same-building must produce distinct fingerprints and distinct uids — the direct regression test for Problem 1a.
- **Willhaben↔Bauträger collapse regression** over real fixture pairs. This is the gate on the accepted fingerprint risk; if it fails, the two-tier design is the documented fallback.
- Per-adapter golden fixtures: trimmed results container, gzipped, ≤50 KB, asserting exact unit count and fields.
- `registry`: alias resolution, duplicate-slug rejection, `wien_active`-without-`offer_url` rejection.
- `pool`: per-domain serialisation; one failing adapter does not abort the run.

**Dashboard**
- Jest over `buildQuery`: multi-select `$in`, parent→alias expansion, empty selection means unconstrained.
- Playwright DOM assertions per cycle on real rendered elements — chips render, search narrows options, counts match `Treffer`, zero-count options disabled, multi-select changes results. Assertions target the visible container, not hidden duplicates. No screenshots into context.
- Final gate: full suite, 0 failures, 0 console errors on `/`, `/dashboard`, `/dashboard/map`, `/coop`.

## Phasing

Each phase ships independently and is verified before the next begins.

**Phase 0 — identity and instrumentation.** `identity`, `coop_uid` + backfill + unique index, strengthened fingerprint, funnel report, aggregate upsert outcomes in `run_coop.py`.
*Expected: 17 → ≥40 units with zero new adapters. This is the highest-value phase and it must be measured before anything else lands.*

**Phase 1 — framework.** `coop_builders.json` with all ~45 GBV orgs, `registry`, `base`, `pool`, `health`. Existing mygewo fetcher ported onto the framework. No new builders yet.

**Phase 2 — filter UX.** `BuilderFilter`, `coopBuilders.ts`, `buildQuery` multi-select.

**Phase 3 — adapters.** Batches of ~8, ordered by inventory size: SOZIALBAU family → BUWOG → WBV-GPA → Wien-Süd → Heimbau → Migra → EBG → GSG → Schwarzatal → the long tail; `covered_by_mygewo` builders last. Each batch gated on green fixtures and a clean health run.

## Out of scope

Handled by other agents; noted only for the dependency.

- **Listing images.**
- **Exact unit addresses on the map.** Phase 0 is a prerequisite: today several real apartments collapse into one document, so unit-level pins cannot be correct before identity is fixed. mygewo already supplies per-unit EWKB coordinates decoded at `genossenschaft_scraper.py:292-310` — the map agent should consume those rather than geocode, and should wait for Phase 0. The registry additionally provides each builder's office address for free.
