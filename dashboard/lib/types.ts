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
  url_is_valid: boolean;
  price_is_estimated?: boolean;
  monatsrate?: number;
  cashNeeded?: number;
  estimated_down_pct?: number;
  estimated_down_pct_kimv?: number;
  estimated_equity_eur?: number;
  bank_score_confidence?: 'low' | 'medium' | 'high';
}

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
  coordinate_source: string;
  landmark_hint: string | null;
  price_is_estimated?: boolean;
  estimated_down_pct?: number;
  estimated_down_pct_kimv?: number;
  estimated_equity_eur?: number;
  bank_score_confidence?: 'low' | 'medium' | 'high';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ListingDetail = any;

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
  coordinate_source: string;
  landmark_hint: string | null;
  price_is_estimated?: boolean;
  estimated_down_pct?: number;
  bank_score_confidence?: 'low' | 'medium' | 'high';
}
