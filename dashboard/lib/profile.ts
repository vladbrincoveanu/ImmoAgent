/**
 * Single source of truth for buyer profile list + display labels on the client.
 * MUST be kept in sync with Project/Application/buyer_profiles.py BUYER_PROFILES keys.
 * Drift test: Tests/test_profile_sync.py asserts equality.
 *
 * 2026-07-06 consolidation (docs/product/value-review-2026-07-06.md): 10 → 5
 * profiles. Removed keys stay accepted as aliases so old URLs / saved searches
 * keep working. Only `default` is free; the 4 personas are Pro-gated.
 */

export interface ProfileMeta {
  key: string;
  label: string;
  description: string;
}

export const PROFILES: ProfileMeta[] = [
  { key: 'default',           label: 'Owner-Occupier',      description: 'Balanced scoring for buying a home to live in' },
  { key: 'budget_buyer',      label: 'First-Time Buyer',    description: 'Enter the market at lowest cost' },
  { key: 'growing_family',    label: 'Growing Family',      description: 'Space, safety, and convenience for children' },
  { key: 'diy_renovator',     label: 'Renovator / Investor', description: 'Add value through renovation and growth potential' },
  { key: 'urban_professional',label: 'Urban Professional',  description: 'Location, lifestyle, modern comforts' },
];

// Removed 2026-07-06: rankings were near-identical to a kept profile
// (Spearman ρ ≥ 0.86 on prod top-100). Aliased so nothing breaks.
export const LEGACY_PROFILE_ALIASES: Record<string, string> = {
  owner_occupier: 'default',
  retiree: 'default',
  eco_conscious: 'urban_professional',
  prime_new_build: 'urban_professional',
  bank_loan_ready: 'urban_professional',
};

export const PROFILE_KEYS: string[] = PROFILES.map((p) => p.key);

export const PROFILE_LABELS: Record<string, string> = Object.fromEntries(
  PROFILES.map((p) => [p.key, p.label]),
);

export const DEFAULT_PROFILE = 'default';

export function isValidProfile(s: string | null | undefined): s is string {
  return typeof s === 'string' && PROFILE_KEYS.includes(s);
}

/** Resolve any input (current key, legacy alias, garbage) to one of the 5 keys. */
export function normalizeProfile(s: string | null | undefined): string {
  if (isValidProfile(s)) return s;
  if (typeof s === 'string' && LEGACY_PROFILE_ALIASES[s]) return LEGACY_PROFILE_ALIASES[s];
  return DEFAULT_PROFILE;
}

/** Every profile except the free default requires Pro. */
export function isProProfile(key: string): boolean {
  return key !== DEFAULT_PROFILE;
}
