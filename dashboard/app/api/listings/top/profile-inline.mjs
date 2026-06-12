export const DEFAULT_PROFILE = 'default';
export const PROFILES = [
  { key: 'default', label: 'Default' },
  { key: 'owner_occupier', label: 'Owner-Occupier' },
  { key: 'diy_renovator', label: 'DIY Renovator' },
  { key: 'growing_family', label: 'Growing Family' },
  { key: 'urban_professional', label: 'Urban Professional' },
  { key: 'eco_conscious', label: 'Eco-Conscious' },
  { key: 'retiree', label: 'Retiree' },
  { key: 'budget_buyer', label: 'Budget Buyer' },
];
const VALID_KEYS = new Set(PROFILES.map((p) => p.key));
export function isValidProfile(s) { return s != null && VALID_KEYS.has(s); }
