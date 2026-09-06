import { Document } from 'mongodb';

export const COLLECTIONS = {
  LISTINGS: 'listings',
} as const;

/** "A listing we are still willing to show" — the canonical active predicate
 * used by /coop, the map, the zone-stats and stats/taken routes. Scrapers
 * insert rows WITHOUT `url_is_valid` (invalidation is the only writer of the
 * field, always `False`), so `{ $ne: false }` — not `true` — is the correct
 * liveness gate. `listing_status: 'taken'` is the explicit off-market marker,
 * set by mark_listing_taken / cleanup. */
export const ACTIVE_LISTING_QUERY: Document = {
  url_is_valid: { $ne: false },
  listing_status: { $ne: 'taken' },
};