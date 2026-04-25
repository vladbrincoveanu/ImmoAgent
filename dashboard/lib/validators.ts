export type SortOption = 'score_desc' | 'price_asc' | 'price_desc' | 'date_desc' | 'area_desc';

const VALID_DISTRICTS = new Set([
  '1010', '1020', '1030', '1040', '1050', '1060', '1070', '1080', '1090',
  '1100', '1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180',
  '1190', '1200', '1210', '1220', '1230',
]);

const VALID_SORT_OPTIONS: SortOption[] = ['score_desc', 'price_asc', 'price_desc', 'date_desc', 'area_desc'];

export function validateDistrict(input: string | null): string | null {
  if (!input || input.trim() === '') return null;
  const trimmed = input.trim();
  return VALID_DISTRICTS.has(trimmed) ? trimmed : null;
}

export function validateSort(input: string | null): SortOption {
  if (!input) return 'score_desc';
  return VALID_SORT_OPTIONS.includes(input as SortOption) ? (input as SortOption) : 'score_desc';
}

export function validateMinScore(input: string | null): number {
  if (!input) return 0;
  const parsed = parseFloat(input);
  if (isNaN(parsed)) return 0;
  return Math.max(0, Math.min(100, parsed));
}

export function validateLimit(input: string | null, max: number): number {
  if (!input) return max;
  const parsed = parseInt(input, 10);
  if (isNaN(parsed)) return max;
  return Math.max(1, Math.min(max, parsed));
}

export function validateObjectId(input: string | null): string | null {
  if (!input) return null;
  return /^[a-fA-F0-9]{24}$/.test(input) ? input : null;
}
