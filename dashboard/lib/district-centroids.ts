// Shared Vienna district centroid coordinates.
// Used for fallback when listings don't have exact coords.
export const DISTRICT_CENTROIDS: Record<string, { lat: number; lon: number }> = {
  '1010': { lat: 48.2082, lon: 16.3716 },
  '1020': { lat: 48.2126, lon: 16.3899 },
  '1030': { lat: 48.2089, lon: 16.3965 },
  '1040': { lat: 48.1984, lon: 16.3850 },
  '1050': { lat: 48.1923, lon: 16.3795 },
  '1060': { lat: 48.1973, lon: 16.3670 },
  '1070': { lat: 48.1991, lon: 16.3538 },
  '1080': { lat: 48.2016, lon: 16.3462 },
  '1090': { lat: 48.2165, lon: 16.3578 },
  '1100': { lat: 48.1856, lon: 16.3775 },
  '1110': { lat: 48.1714, lon: 16.4194 },
  '1120': { lat: 48.1901, lon: 16.3452 },
  '1130': { lat: 48.1939, lon: 16.2833 },
  '1140': { lat: 48.2090, lon: 16.3047 },
  '1150': { lat: 48.1975, lon: 16.3123 },
  '1160': { lat: 48.2135, lon: 16.3153 },
  '1170': { lat: 48.2236, lon: 16.3044 },
  '1180': { lat: 48.2256, lon: 16.2848 },
  '1190': { lat: 48.2359, lon: 16.3047 },
  '1200': { lat: 48.2352, lon: 16.3654 },
  '1210': { lat: 48.2446, lon: 16.3936 },
  '1220': { lat: 48.2427, lon: 16.4345 },
  '1230': { lat: 48.1508, lon: 16.3155 },
};

export function getDistrictCentroid(bezirk: string | null | undefined): { lat: number; lon: number } | null {
  if (!bezirk) return null;
  return DISTRICT_CENTROIDS[bezirk] ?? null;
}

export function resolveCoordinates(
  storedCoords: { lat: number; lon: number } | null | undefined,
  bezirk: string | null | undefined
): { lat: number; lon: number } | null {
  if (storedCoords && typeof storedCoords.lat === 'number' && typeof storedCoords.lon === 'number') {
    return storedCoords;
  }
  return getDistrictCentroid(bezirk);
}
