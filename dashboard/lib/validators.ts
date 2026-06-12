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
  if (VALID_DISTRICTS.has(trimmed)) return trimmed;
  const SHORT_TO_LONG: Record<string, string> = {
    '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
    '6': '1060', '7': '1070', '8': '1080', '9': '1090',
    '01': '1010', '02': '1020', '03': '1030', '04': '1040', '05': '1050',
    '06': '1060', '07': '1070', '08': '1080', '09': '1090',
    '10': '1100', '11': '1110', '12': '1120', '13': '1130', '14': '1140',
    '15': '1150', '16': '1160', '17': '1170', '18': '1180', '19': '1190',
    '20': '1200', '21': '1210', '22': '1220', '23': '1230',
  };
  return SHORT_TO_LONG[trimmed] ?? null;
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

export type StatusOption = 'all' | 'active' | 'taken';
export function validateStatus(input: string | null): StatusOption {
  if (!input) return 'all';
  return (['all', 'active', 'taken'].includes(input)) ? input as StatusOption : 'all';
}
