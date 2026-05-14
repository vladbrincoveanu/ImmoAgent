export type FilterState = {
  minScore: string;
  district: string;
  sortBy: string;
  maxPrice: string;
  showUnfinanceable: boolean;
};

export function filtersFromParams(searchParams: URLSearchParams): FilterState {
  return {
    minScore: searchParams.get('min_score') ?? '0',
    district: searchParams.get('district') ?? '',
    sortBy: searchParams.get('sort') ?? 'score_desc',
    maxPrice: searchParams.get('max_price') ?? '500000',
    showUnfinanceable: searchParams.get('unfinanceable') === 'true',
  };
}

export function paramsFromFilters(filters: FilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.minScore && filters.minScore !== '0') params.set('min_score', filters.minScore);
  if (filters.district) params.set('district', filters.district);
  if (filters.sortBy && filters.sortBy !== 'score_desc') params.set('sort', filters.sortBy);
  if (filters.maxPrice && filters.maxPrice !== '500000') params.set('max_price', filters.maxPrice);
  if (filters.showUnfinanceable) params.set('unfinanceable', 'true');
  return params;
}