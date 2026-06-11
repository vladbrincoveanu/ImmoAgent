import { DEFAULT_PROFILE, isValidProfile } from './profile';

export type FilterState = {
  minScore: string;
  district: string;
  sortBy: string;
  maxPrice: string;
  showUnfinanceable: boolean;
  equity: string;
  rate: string;
  maxEquity: string;
  profile: string;
  belowAvgPct: string;
  destName: string;
  destLat: string;
  destLon: string;
  maxCommute: string;
};

export function filtersFromParams(searchParams: URLSearchParams): FilterState {
  const rawProfile = searchParams.get('profile');
  return {
    minScore: searchParams.get('min_score') ?? '0',
    district: searchParams.get('district') ?? '',
    sortBy: searchParams.get('sort') ?? 'score_desc',
    maxPrice: searchParams.get('max_price') ?? '500000',
    showUnfinanceable: searchParams.get('unfinanceable') === 'true',
    equity: searchParams.get('equity') ?? '100000',
    rate: searchParams.get('rate') ?? '3.8',
    maxEquity: searchParams.get('max_equity') ?? '',
    profile: isValidProfile(rawProfile) ? (rawProfile as string) : DEFAULT_PROFILE,
    belowAvgPct: searchParams.get('below_avg_pct') ?? '',
    destName: searchParams.get('dest_name') ?? '',
    destLat: searchParams.get('dest_lat') ?? '',
    destLon: searchParams.get('dest_lon') ?? '',
    maxCommute: searchParams.get('max_commute') ?? '',
  };
}

export function paramsFromFilters(filters: FilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.minScore && filters.minScore !== '0') params.set('min_score', filters.minScore);
  if (filters.district) params.set('district', filters.district);
  if (filters.sortBy && filters.sortBy !== 'score_desc') params.set('sort', filters.sortBy);
  if (filters.maxPrice && filters.maxPrice !== '500000') params.set('max_price', filters.maxPrice);
  if (filters.showUnfinanceable) params.set('unfinanceable', 'true');
  if (filters.equity && filters.equity !== '100000') params.set('equity', filters.equity);
  if (filters.rate && filters.rate !== '3.8') params.set('rate', filters.rate);
  if (filters.maxEquity) params.set('max_equity', filters.maxEquity);
  if (filters.belowAvgPct) params.set('below_avg_pct', filters.belowAvgPct);
  if (filters.destName) {
    params.set('dest_name', filters.destName);
    if (filters.destLat) params.set('dest_lat', filters.destLat);
    if (filters.destLon) params.set('dest_lon', filters.destLon);
  }
  if (filters.maxCommute) params.set('max_commute', filters.maxCommute);
  // Always set profile so URL is shareable
  if (filters.profile && filters.profile !== DEFAULT_PROFILE) params.set('profile', filters.profile);
  return params;
}
