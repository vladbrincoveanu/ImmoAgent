import { DEFAULT_PROFILE } from './profile';
import type { CoordinateSource, MapListing } from './types';
import { resolveCoordinates } from './district-centroids';
import type { SortOption } from './validators';

export const MAP_PROJECTION: Record<string, 1> = {
  title: 1,
  url: 1,
  source_enum: 1,
  bezirk: 1,
  price_total: 1,
  area_m2: 1,
  rooms: 1,
  score: 1,
  scores: 1,
  image_url: 1,
  coordinates: 1,
  coordinate_source: 1,
  landmark_hint: 1,
  estimated_down_pct: 1,
  estimated_down_pct_kimv: 1,
  estimated_equity_eur: 1,
  bank_score_confidence: 1,
  ubahn_walk_minutes: 1,
  is_genossenschaft: 1,
};

export const TOP_PROJECTION: Record<string, 1> = {
  ...MAP_PROJECTION,
  processed_at: 1,
  price_history: 1,
  address: 1,
  url_is_valid: 1,
  minio_image_path: 1,
};

export type ListingMode = 'purchase' | 'coop';

type ListingDocument = {
  _id: { toString(): string };
  [key: string]: unknown;
};

type MapListingResponse = MapListing & {
  scores: Record<string, number | null> | null;
  profile: string;
};

type TopListingResponse = MapListingResponse & {
  processed_at: number | null;
  url_is_valid: boolean;
  price_history: Array<{ price_total: number; date: number }> | null;
  address: string | null;
};

type MapPresentationOptions = {
  profile: string;
  pricePerSqm: number;
  zoneAverage?: number;
};

type DetailPresentationOptions = {
  profile: string;
};

const COORDINATE_SOURCES = new Set<CoordinateSource>(['exact', 'landmark', 'district', 'none']);

const DETAIL_FIELDS = [
  'url', 'title', 'bezirk', 'address', 'source_enum', 'price_total', 'area_m2', 'rooms',
  'year_built', 'floor', 'condition', 'heating', 'parking', 'betriebskosten', 'hwb_value',
  'fgee_value', 'energy_class', 'heating_type', 'energy_carrier', 'available_from',
  'special_features', 'price_per_m2', 'monatsrate', 'own_funds', 'image_url',
  'sent_to_telegram', 'processed_at', 'local_image_path', 'coordinate_source', 'landmark_hint',
  'potential_growth_rating', 'renovation_needed_rating', 'balcony_terrace', 'floor_level',
  'street_view', 'orientation', 'lift_present', 'facade_renovated', 'parifizierung_complete',
  'roof_renovated', 'building_condition', 'floor_surface', 'free_area_m2', 'unit_number',
  'ruecklage_eur_month', 'kitchen_included', 'window_type', 'sonderumlage_risk', 'doppelmakler',
  'maklerprovision_pct', 'document_urls', 'parent_project_id', 'belehnungswert_factor',
  'estimated_down_pct', 'estimated_down_pct_kimv', 'estimated_equity_eur', 'bank_score_confidence',
  'betriebskosten_breakdown', 'score_breakdown', 'ubahn_walk_minutes', 'school_walk_minutes',
  'infrastructure_distances', 'mortgage_details', 'structured_analysis', 'price_history',
  'url_is_valid', 'price_is_estimated', 'regulatory', 'green_infra', 'gratzl_id', 'investment',
] as const;

export function buildListingSort(
  profile: string,
  sort: SortOption,
  mode: ListingMode = 'purchase',
): Record<string, 1 | -1> {
  const options: Record<SortOption, Record<string, 1 | -1>> = {
    score_desc: profile === DEFAULT_PROFILE
      ? { score: -1, processed_at: -1 }
      : { [`scores.${profile}`]: -1, processed_at: -1 },
    price_asc: { price_total: 1 },
    price_desc: { price_total: -1 },
    date_desc: { processed_at: -1 },
    area_desc: { area_m2: -1 },
  };

  return mode === 'coop' && sort === 'score_desc'
    ? options.date_desc
    : options[sort] ?? options.score_desc;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

function numberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' ? value : undefined;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function readCoordinates(value: unknown): { lat: number; lon: number } | null {
  if (!value || typeof value !== 'object') return null;
  const coordinates = value as { lat?: unknown; lon?: unknown };
  return typeof coordinates.lat === 'number' && typeof coordinates.lon === 'number'
    ? { lat: coordinates.lat, lon: coordinates.lon }
    : null;
}

function readScores(value: unknown): Record<string, number | null> | null {
  if (!value || typeof value !== 'object') return null;
  const scores: Record<string, number | null> = {};
  for (const [key, score] of Object.entries(value)) {
    if (typeof score === 'number' || score === null) scores[key] = score;
  }
  return Object.keys(scores).length > 0 ? scores : null;
}

export function presentMapListing(
  doc: ListingDocument,
  { profile, pricePerSqm, zoneAverage }: MapPresentationOptions,
): MapListingResponse {
  const area = numberOrNull(doc.area_m2);
  const hasPrice = typeof doc.price_total === 'number' && doc.price_total > 0;
  const price_is_estimated = !hasPrice && area != null && area > 0;
  const price_total = hasPrice
    ? doc.price_total as number
    : price_is_estimated
      ? Math.round(area * pricePerSqm)
      : null;

  const storedCoords = readCoordinates(doc.coordinates);
  const bezirk = stringOrNull(doc.bezirk);
  const coordinates = resolveCoordinates(storedCoords, bezirk);
  const rawSource = typeof doc.coordinate_source === 'string' ? doc.coordinate_source : 'none';
  const coordinate_source: CoordinateSource = !coordinates
    ? 'none'
    : !storedCoords
      ? 'district'
      : COORDINATE_SOURCES.has(rawSource as CoordinateSource) && rawSource !== 'none'
        ? rawSource as CoordinateSource
        : 'exact';

  const scores = readScores(doc.scores);
  const score = scores?.[profile] ?? numberOrNull(doc.score);
  const price_vs_avg_pct = price_total != null && zoneAverage != null && zoneAverage > 0
    ? Math.round(((price_total - zoneAverage) / zoneAverage) * 100)
    : null;

  return {
    _id: doc._id.toString(),
    title: stringOrNull(doc.title),
    url: typeof doc.url === 'string' ? doc.url : '',
    source_enum: typeof doc.source_enum === 'string' ? doc.source_enum : '',
    bezirk,
    price_total,
    area_m2: area,
    rooms: numberOrNull(doc.rooms),
    score,
    scores,
    profile,
    image_url: stringOrNull(doc.image_url),
    coordinates,
    coordinate_source,
    landmark_hint: stringOrNull(doc.landmark_hint),
    price_is_estimated,
    estimated_down_pct: numberOrUndefined(doc.estimated_down_pct),
    estimated_down_pct_kimv: numberOrUndefined(doc.estimated_down_pct_kimv),
    estimated_equity_eur: numberOrUndefined(doc.estimated_equity_eur),
    bank_score_confidence: doc.bank_score_confidence as MapListing['bank_score_confidence'],
    price_vs_avg_pct,
    ubahn_walk_minutes: numberOrNull(doc.ubahn_walk_minutes),
    is_genossenschaft: doc.is_genossenschaft === true,
  };
}

export function presentTopListing(
  doc: ListingDocument,
  options: MapPresentationOptions,
): TopListingResponse {
  const base = presentMapListing(doc, options);
  const image_url = stringOrNull(doc.image_url) || stringOrNull(doc.minio_image_path);
  const price_history = Array.isArray(doc.price_history)
    ? doc.price_history as Array<{ price_total: number; date: number }>
    : null;

  return {
    ...base,
    image_url,
    processed_at: numberOrNull(doc.processed_at),
    url_is_valid: doc.url_is_valid !== false,
    price_history,
    address: stringOrNull(doc.address),
  };
}

export function presentListingDetail(
  doc: ListingDocument,
  { profile }: DetailPresentationOptions,
): Record<string, unknown> {
  const result: Record<string, unknown> = { _id: doc._id.toString() };
  for (const field of DETAIL_FIELDS) {
    if (field in doc) result[field] = doc[field];
  }

  const storedCoords = readCoordinates(doc.coordinates);
  const coordinates = resolveCoordinates(storedCoords, stringOrNull(doc.bezirk));
  const scores = readScores(doc.scores);

  result.score = scores?.[profile] ?? numberOrNull(doc.score);
  result.profile = profile;
  result.coordinates = coordinates;

  if (!('coordinate_source' in result)) {
    result.coordinate_source = !coordinates
      ? 'none'
      : storedCoords
        ? 'exact'
        : 'district';
  }

  return result;
}
