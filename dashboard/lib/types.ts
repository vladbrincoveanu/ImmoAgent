export type CoordinateSource = 'exact' | 'landmark' | 'district' | 'none';

export type BankScoreConfidence = 'low' | 'medium' | 'high';

export interface Coordinates {
  lat: number;
  lon: number;
}

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
  bank_score_confidence?: BankScoreConfidence;
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
  coordinates: Coordinates | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
  price_is_estimated?: boolean;
  estimated_down_pct?: number;
  estimated_down_pct_kimv?: number;
  estimated_equity_eur?: number;
  bank_score_confidence?: BankScoreConfidence;
}

export interface MortgageDetails {
  own_funds?: number | null;
  monatsrate?: number | null;
  interest_rate?: number | null;
  loan_years?: number | null;
  down_payment_pct?: number | null;
  calculated_monatsrate?: number | null;
  total_monthly_cost?: number | null;
}

export interface RegulatoryProfile {
  rent_regulated: boolean | null;
  rent_regulated_source: 'regex' | 'inferred' | null;
}

export interface GreenInfraProfile {
  nearest_wieneu_zone: string | null;
  anergy_distance_m: number | null;
  subsidy_eligible: boolean | null;
}

export interface InvestmentProfile {
  estimated_rental_yield_pct: number | null;
  estimated_monthly_rent_eur: number | null;
  price_per_m2_history: Array<{ date: string; eur_per_m2: number }> | null;
}

export interface ListingDetail {
  _id: string;
  url: string;
  title: string | null;
  bezirk: string | null;
  address: string | null;
  source_enum: string;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  year_built: number | null;
  floor: number | null;
  condition: string | null;
  heating: string | null;
  parking: string | null;
  betriebskosten: number | null;
  hwb_value: number | null;
  fgee_value: number | null;
  energy_class: string | null;
  heating_type: string | null;
  energy_carrier: string | null;
  available_from: string | null;
  special_features: string[];
  price_per_m2: number | null;
  monatsrate: number | null;
  own_funds: number | null;
  score: number | null;
  image_url: string | null;
  sent_to_telegram: boolean;
  processed_at: number | null;
  local_image_path: string | null;
  coordinates: Coordinates | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
  potential_growth_rating: number | null;
  renovation_needed_rating: number | null;
  balcony_terrace: boolean | null;
  floor_level: number | null;
  street_view: number | null;
  orientation: number | null;
  lift_present: boolean | null;
  facade_renovated: boolean | null;
  parifizierung_complete: boolean | null;
  roof_renovated: boolean | null;
  building_condition: string | null;
  floor_surface: string | null;
  free_area_m2: number | null;
  unit_number: string | null;
  ruecklage_eur_month: number | null;
  kitchen_included: boolean | null;
  window_type: string | null;
  sonderumlage_risk: boolean | null;
  doppelmakler: boolean | null;
  maklerprovision_pct: number | null;
  document_urls: Record<string, string> | null;
  parent_project_id: number | null;
  belehnungswert_factor: number | null;
  estimated_down_pct: number | null;
  estimated_down_pct_kimv: number | null;
  estimated_equity_eur: number | null;
  bank_score_confidence: BankScoreConfidence | null;
  betriebskosten_breakdown: Record<string, number> | null;
  score_breakdown: Record<string, number> | null;
  ubahn_walk_minutes: number | null;
  school_walk_minutes: number | null;
  infrastructure_distances: Record<string, number | string>;
  mortgage_details: MortgageDetails | null;
  structured_analysis: Record<string, unknown> | null;
  url_is_valid: boolean;
  price_is_estimated: boolean | null;
  regulatory: RegulatoryProfile | null;
  green_infra: GreenInfraProfile | null;
  gratzl_id: string | null;
  investment: InvestmentProfile | null;
}
