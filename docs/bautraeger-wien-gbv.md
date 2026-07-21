# Vienna Bauträger (GBV) — crawl reference

Extracted from `Downloads/Bauträgeradressen.pdf` = the official **GBV Bauträgerliste Wien**
(Bundesland W), Stand **01.10.2022** (`gbv.at/Mitglied/Bundesland/W`). This is the
authoritative registry of Vienna's non-profit housing developers (gemeinnützige
Bauvereinigungen) we source co-op rentals from.

- **Structured data:** `Project/data/bautraeger_wien.json` (64 entries: name, web, email,
  phone, HQ address, brand-alias, mygewo coverage).
- **64 entries**, of which **19 are brand-aliases** that route to a parent
  (`"siehe X"` in the PDF), e.g. DAHEIM/DOMIZIL/WIENER HEIM → **MISCHEK**;
  FAMILIE/NEULAND/URBANBAU/VINDOBONA/VOLKSBAU/WOHNBAU → **SOZIALBAU**;
  KROTTENBACH/Wohnungseigentum → **ÖSW**; PATRIA/WIENER → **ÖVW**;
  STEG/WOHNPARK ALT ERLAA → **GESIBA**; MERKUR → **WIEN SÜD**;
  WEVAG/Fonds temporäres Wohnen → **ARWAG**; EISENHOF → **HEIMBAU**.
- 3 have a non-Wien HQ but are GBV-W members: ALPENLAND (3100 St. Pölten),
  die EIGENTUM (2334 Vösendorf), GEBÖS (2521 Trumau).

## How we crawl these: mygewo.at (single aggregator)

We do **not** scrape each builder site individually. **mygewo.at aggregates the Vienna
co-op rental inventory** of ~12 of these builders into one search. The scraper
(`Project/Application/scraping/genossenschaft_scraper.py → fetch_all_mygewo`) crawls the
**full** Wien inventory by paging through mygewo's TanStack server-function RPC
(`states=28_` = Wien), decoding its seroval-JSON response, and keeping rentals only
(`buyable` buy-option units are dropped).

### mygewo Wien snapshot (2026-07-21, verified)

| Metric | Value |
|---|---|
| Total Wien units mygewo reports | **75** |
| Rentals ingested (buy-option dropped) | **58** |
| Buy-option units filtered out | 17 |
| Builders with live Wien inventory | 11 |

Builders observed in mygewo's live Wien feed: **ÖVW** (22), **ÖSW** (10),
**Familienwohnbau** (6), **GESIBA** (5), **Siedlungsunion** (3), **Heimbau** (3),
**ARWAG** (2), **Frieden** (2), **Neues Leben** (1), **BWSG** (1), plus
**LebenswertWohnen** (3) — the last aggregated by mygewo but not itself a GBV-W member.

> ⚠️ Prior to this change the scraper parsed only mygewo's server-rendered **first page**
> (~25 units → 21 rentals), silently dropping ~2/3 of the inventory. `fetch_all_mygewo`
> now pages through everything. See `Tests/test_mygewo_rpc.py` for the offline coverage.

Builders in the PDF that mygewo does **not** currently surface for Wien (no live rental
inventory in the snapshot, or they publish only on their own site) are listed with their
`web` URL in the JSON and can be added as standalone adapters if a gap is confirmed.
