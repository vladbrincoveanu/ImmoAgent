'use client';

import { useCallback, useMemo } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { filtersFromParams, paramsFromFilters, type FilterState } from './filters';

export function useFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const state = useMemo(() => filtersFromParams(sp), [sp]);

  const update = useCallback(
    (patch: Partial<FilterState>) => {
      const next: FilterState = { ...state, ...patch };
      const params = paramsFromFilters(next);
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
    },
    [state, router, pathname],
  );

  return { ...state, update };
}
