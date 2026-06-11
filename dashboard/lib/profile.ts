/**
 * Single source of truth for buyer profile list + display labels on the client.
 * MUST be kept in sync with Project/Application/buyer_profiles.py BUYER_PROFILES keys.
 * Drift test: Tests/test_profile_sync.py asserts equality.
 */

export interface ProfileMeta {
  key: string;
  label: string;
  description: string;
}

export const PROFILES: ProfileMeta[] = [
  { key: 'default',           label: 'Default',            description: 'Balanced scoring for general property evaluation' },
  { key: 'owner_occupier',    label: 'Owner-Occupier',     description: 'Newer, efficient homes with low renovation needs' },
  { key: 'diy_renovator',     label: 'DIY Renovator',      description: 'Actively seeking properties to add value through renovation' },
  { key: 'growing_family',    label: 'Growing Family',     description: 'Space, safety, and convenience for children' },
  { key: 'urban_professional',label: 'Urban Professional', description: 'Location, lifestyle, modern comforts' },
  { key: 'eco_conscious',     label: 'Eco-Conscious',      description: 'Sustainability, energy efficiency, low carbon footprint' },
  { key: 'retiree',           label: 'Retiree',            description: 'Comfort, accessibility, peaceful living' },
  { key: 'budget_buyer',      label: 'Budget Buyer',       description: 'Enter the market at lowest cost' },
  { key: 'prime_new_build',   label: 'Prime New Build',    description: 'New/recent construction in good zones' },
  { key: 'bank_loan_ready',   label: 'Bank Loan Ready',    description: 'Austrian bank Belehnungswert criteria; missing fields score 0' },
];

export const PROFILE_KEYS: string[] = PROFILES.map((p) => p.key);

export const PROFILE_LABELS: Record<string, string> = Object.fromEntries(
  PROFILES.map((p) => [p.key, p.label]),
);

export const DEFAULT_PROFILE = 'default';

export function isValidProfile(s: string | null | undefined): s is string {
  return typeof s === 'string' && PROFILE_KEYS.includes(s);
}
