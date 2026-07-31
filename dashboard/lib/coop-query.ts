import { Document } from 'mongodb';

// Parking spots / storage units occasionally slip through a builder's own site
// tagged as "Wohnung" (e.g. a 12,5 m² Stellplatz) — below this, it isn't housing.
export const MIN_LIVABLE_AREA_M2 = 15;

/** The single definition of "a co-op unit we are willing to show", shared by
 * /coop and the map. Both surfaces MUST import this: when they each kept their
 * own copy, the map's purchase-tuned €/m² floor silently excluded every co-op
 * rental while /coop listed them, and nothing flagged the divergence.
 *
 * Co-op RENTALS have a low €/m² and no purchase price, so the purchase-tuned
 * filters deliberately do not appear here.
 * Builder-direct only: Willhaben-sourced rows are excluded because they link
 * to Willhaben (not the builder's reservation page) and can leak mis-tagged
 * for-sale (Eigentum) units in as rentals.
 * buyable:false is a POSITIVE rental confirmation the poller stamps on every
 * unit it emits (buy-option units are dropped at scrape). Requiring it (not
 * just $ne:true) also hides legacy rows scraped before this flag existed —
 * they reappear within one poll cycle once re-scraped as rentals.
 * bezirk + area_m2 are a defense-in-depth guard, independent of the flags
 * above: the (now-disabled) standalone ÖVW/Familienwohnbau/BWSG adapters had
 * no Vienna scoping and no housing-size floor, so a stray non-Wien or
 * garage/storage row must never render regardless of DB state. */
/** "A private co-op transfer we are willing to show" — the /coop/private rubric.
 *
 * Deliberately NOT coopBaseQuery() with a flag flipped. That query is
 * builder-direct by construction: it excludes `coop_source: 'willhaben'` and
 * requires the `buyable:false` stamp that only the mygewo poller writes. Private
 * transfers are the exact opposite — they are Willhaben ads, and no builder ever
 * stamps them. Sharing one query would mean either letting for-sale units leak
 * into /coop or showing nothing here.
 *
 * `coop_kind` is the whole gate: it is written only after BOTH a transfer marker
 * and a co-op marker matched (see extract_is_private_coop_transfer), so a fitted-
 * kitchen Ablöse on an ordinary rental never reaches this page.
 *
 * bezirk + area_m2 mirror the builder-direct guard: a stray non-Wien row or a
 * garage tagged "Wohnung" must not render regardless of DB state. */
export function privateCoopQuery(): Document {
  return {
    coop_kind: 'private_transfer',
    url_is_valid: { $ne: false },
    bezirk: { $regex: '^1\\d{3}$' },
    $or: [{ area_m2: null }, { area_m2: { $gte: MIN_LIVABLE_AREA_M2 } }],
  };
}

export function coopBaseQuery(): Document {
  return {
    is_genossenschaft: true,
    url_is_valid: { $ne: false },
    coop_source: { $ne: 'willhaben' },
    buyable: false,
    bezirk: { $regex: '^1\\d{3}$' },
    // { area_m2: null } already matches missing/undefined fields in MongoDB —
    // no separate $exists:false clause needed.
    $or: [{ area_m2: null }, { area_m2: { $gte: MIN_LIVABLE_AREA_M2 } }],
  };
}
