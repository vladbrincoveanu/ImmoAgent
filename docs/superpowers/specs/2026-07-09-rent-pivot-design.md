# RENT Pivot — Brainstorm Summary (mid-design)

**Date:** 2026-07-09
**Status:** 🟡 IN PROGRESS — brainstorm, not yet a committed spec. Product loop defined; core fork + several branches still OPEN.
**Goal of pivot:** Add a RENT product to immo-scouter that is *additive* (keep the existing buy/for-sale product), has a *real moat*, and monetizes something renters will *actually pay for*.

---

## 1. What we KILLED (settled, do not revisit)

- **Paid "vet / score a listing" for general renters.** Renters don't pay for search or info.
  - Landlord-pays is the market norm; Willhaben is free; renters are price-sensitive.
  - "Fair price" is already free via Flatbee Preisbarometer.
  - **Conclusion: info = free. Not a product.**

- **Success fee (25–40% of one month's rent).** Unenforceable for us.
  - We are **NOT in the transaction** — the flat is on Willhaben, the contract is signed offline.
  - We can't capture a % of a deal that happens outside our platform. Money leaks.
  - (This is *why* the money question got deferred — see §5.)

---

## 2. What we NAILED (settled direction)

- **The only proven renter-payer = people MOVING TO VIENNA FROM ABROAD** (expats / students / relocators).
  - Proof point: **HousingAnywhere** — renter pays 25–40% of a month's rent, ~€1.2B/yr gross bookings, 160k listings, 125+ cities.
  - They pay because they **can't view in person**, are **scared of scams** (Vienna ≈ 30 scams/week), and are **time-boxed** (fixed move date).

- **Direction C = HYBRID** (chosen over pure-marketplace and pure-tool):
  - Our existing scraper engine **+** target incomers **+** done-for-you relocation (vet listings, scam-check, help fire the application).
  - Reuses what we already built; aims at a *proven* payer instead of the price-sensitive general renter.

- **Proven clone/reference targets:**
  | Company | Model |
  |---|---|
  | HousingAnywhere | renter-pays booking marketplace |
  | Wunderflats | furnished mid-term, B2B landlord-commission, corporate clients |
  | Flatly (Berlin) | 16-portal aggregation bot (we're ~80% here already) |
  | ImmoScout MieterPlus | paid queue-jump / priority applicant |
  | Rently | verified/scam-free listings, charges B2B |
  | Getmomo / Moneyfix | deposit financing (monthly fee vs cash deposit) |

---

## 3. The PRODUCT LOOP (defined this session)

The service, step by step:

1. **Intake** — user gives criteria (budget, area, move-in date, furnished?, household).
2. **Match** — surface flats that fit (from our scraper). → *table-stakes, NOT the value (free on Willhaben).*
3. **Verify** — confirm each listing is real, not a scam. → *real value (Vienna ≈ 30 scams/wk).*
4. **Dossier** — assemble their application packet in the German format landlords expect
   (Selbstauskunft, 3× payslips, Meldezettel, ID, cover letter, guarantor letter). → *high value in Vienna: whoever has the packet ready wins; light/template product.*
5. **Apply** — submit applications on their behalf, fast. → *the moneymaker AND the landmine.*
6. **Land** — user gets a viewing / an offer.

Per-step verdicts:
- **Match** is not the product — everyone has it free.
- **Verify** is genuine value but its *mechanism* is unresolved (software vs. human — see §4).
- **Dossier** is real but mostly a smart form + checklist + German-format assembly. We can't manufacture the user's documents.
- **Apply** is where value and risk concentrate.

---

## 4. OPEN QUESTIONS (must resolve before spec)

### 4.1 ⭐ THE CRUX FORK — what kind of company is this?
- **(A) "We do it FOR you"** — done-for-you relocation *agency* with software. We make the calls, fire the applications, human-in-the-loop. Higher value, higher trust, **does not scale cheaply**.
- **(B) "We make you 10× faster"** — self-serve *SaaS tool*. Verified-listing flags + one-tap dossier; the **user still acts**. Scales, but weaker "magic."
- These are two genuinely different companies. **NOT YET DECIDED.** (This is the question the user was asked last.)

### 4.2 Who exactly is the customer? (three hidden products)
- **Student** — Sept intake, budget, wants a room/WG, 6–12 mo.
- **Corporate relocator** — company-sponsored, furnished, 3–12 mo, less price-sensitive.
- **Job-mover settling permanently** — wants a real long-lease unfurnished flat (our existing inventory).

### 4.3 Inventory mismatch (the landmine)
- Our scraper today = **unfurnished, long-lease / for-sale** Vienna flats.
- Incomers who can't view in person mostly want **furnished mid-term**.
- Serve them → we must scrape a *different* market (Wunderflats / HousingAnywhere inventory).
- Serve the long-lease subset → we reuse our engine, but the "can't view in person" pain is weaker.
- **Note:** #4.3 (inventory) forces #4.2 (customer) — flat type dictates who shows up.

### 4.4 Verify mechanism (decides if it scales)
- Software check (reverse-image photos, cross-check agent/landlord, sanity-check price vs Preisbarometer)?
- Or a human doing legwork (calling to confirm)?

### 4.5 Apply mechanism (value vs. ToS risk)
- **(a)** Auto-fire applications into Willhaben contact forms → the "magic," but hits portal ToS, scam-flag risk, semi-auto at best.
- **(b)** Hand user a ready-to-send dossier + the contact; they hit send → honest but we're "just" a dossier tool.

---

## 5. MONEY MODEL (deferred — resolve AFTER §4)

Success fee is out (§1). Remaining clean options, to be decided once the product is defined:
- **Upfront service fee** — €150–400 flat, card on file, charged before work. Enforceable, no capture leak. Risk: cold-start trust (pay before results).
- **Deposit guarantee** — we/bank partner (e.g. Getmomo, ~5.5%/yr) cover the 3-month cash deposit; renter pays a monthly fee. High perceived value (frees cash). Risk: needs bank partner + Austrian Mietrechtsgesetz regulation; v2 timeline.
- **Both, phased** — launch on upfront fee, add deposit guarantee as v2.

**User's steer this session:** don't lock the money model until the actual product ("the thing we will do") is finished being defined. Money is downstream of §4.

---

## 6. STANDING RISKS

- **Payment capture** — we're not in the transaction; clean money = upfront fee or deposit, not success fee.
- **Inventory mismatch** — furnished mid-term vs. our long-lease/for-sale scraper.
- **Cold-start on trust** — a done-for-you service must earn trust before users pre-pay.
- **Deposit guarantee** — needs a bank partner + AT regulatory work.
- **One-tap apply** — auto-firing hits portal ToS; semi-auto at best in v1.

---

## 7. NEXT SINGLE STEP

Resolve **§4.1 (the crux fork): done-for-you agency (A) vs. self-serve SaaS tool (B).**
That decision cascades into customer (§4.2), inventory (§4.3), verify/apply mechanisms (§4.4–4.5), and only then the money model (§5). Then grill-me → promote this file from summary to committed spec.

---

## Key files (for whoever implements)
- `Project/Application/scraping/willhaben_scraper.py`
- `Project/Application/helpers/utils.py:281` (search URLs)
- `Project/Application/scoring.py` (`NORMALIZATION_RANGES`)
- `Project/Application/helpers/listing_validator.py:72`
- `Project/Domain/constants.py` (`RENTAL_KEYWORDS`)
- `dashboard/lib/{types.ts,profile.ts}`
- `docs/superpowers/specs/2026-06-09-rent-regulated-layer-design.md` (prior rent work)
