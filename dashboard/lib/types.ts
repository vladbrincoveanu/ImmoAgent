export interface ListingBase {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  processed_at: number | null;
  image_url: string | null;
}

export type CoordinateSource = 'exact' | 'landmark' | 'none';

export interface MapListing {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  image_url: string | null;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
}

export interface ListingDetail extends ListingBase {
  address: string | null;
  year_built: number | null;
  floor: number | null;
  condition: string | null;
  heating: string | null;
  parking: string | null;
  betriebskosten: number | null;
  energy_class: string | null;
  hwb_value: number | null;
  fgee_value: number | null;
  rooms: number | null;
  calculated_monatsrate: number | null;
  total_monthly_cost: number | null;
  ubahn_walk_minutes: number | null;
  school_walk_minutes: number | null;
  infrastructure_distances: Record<string, unknown>;
  score_breakdown?: Record<string, number>;
  url_is_valid?: boolean;
  coordinate_source?: CoordinateSource;
  landmark_hint?: string | null;
}

export interface TopListingsResponse {
  listings: ListingBase[];
  total: number;
}
