from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from Domain.sources import Source
from Domain.location import Coordinates

@dataclass
class Listing:
    """Represents a single real estate listing."""
    url: str
    source: Source
    title: Optional[str] = None
    bezirk: Optional[str] = None
    address: Optional[str] = None
    price_total: Optional[float] = None
    area_m2: Optional[float] = None
    rooms: Optional[float] = None
    year_built: Optional[int] = None
    floor: Optional[int] = None
    condition: Optional[str] = None
    heating: Optional[str] = None
    parking: Optional[str] = None
    betriebskosten: Optional[float] = None
    betriebskosten_estimated: Optional[bool] = None
    energy_class: Optional[str] = None
    hwb_value: Optional[float] = None
    fgee_value: Optional[float] = None
    heating_type: Optional[str] = None
    energy_carrier: Optional[str] = None
    available_from: Optional[str] = None
    special_features: Optional[List[str]] = field(default_factory=list)
    monatsrate: Optional[float] = None
    own_funds: Optional[float] = None
    price_per_m2: Optional[float] = None
    ubahn_walk_minutes: Optional[int] = None
    school_walk_minutes: Optional[int] = None
    calculated_monatsrate: Optional[float] = None
    mortgage_details: Optional[Dict[str, Any]] = field(default_factory=dict)
    total_monthly_cost: Optional[float] = None
    infrastructure_distances: Dict[str, Any] = field(default_factory=dict)
    image_url: Optional[str] = None
    structured_analysis: Optional[Dict[str, Any]] = field(default_factory=dict)
    sent_to_telegram: bool = False
    processed_at: Optional[float] = None
    local_image_path: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    coordinate_source: Optional[str] = None  # 'exact' | 'landmark' | 'none'
    landmark_hint: Optional[str] = None
    source_enum: Optional[Source] = None
    score: Optional[float] = None
    potential_growth_rating: Optional[int] = None
    renovation_needed_rating: Optional[int] = None
    balcony_terrace: Optional[bool] = None
    floor_level: Optional[int] = None
    street_view: Optional[int] = None
    orientation: Optional[int] = None
    lift_present: Optional[bool] = None
    facade_renovated: Optional[bool] = None
    parifizierung_complete: Optional[bool] = None
    roof_renovated: Optional[bool] = None
    building_condition:    Optional[str]        = None
    floor_surface:         Optional[str]        = None
    free_area_m2:          Optional[float]      = None
    unit_number:           Optional[str]        = None
    ruecklage_eur_month:   Optional[float]      = None
    kitchen_included:      Optional[bool]       = None
    window_type:           Optional[str]        = None
    sonderumlage_risk:     Optional[bool]       = None
    doppelmakler:          Optional[bool]       = None
    maklerprovision_pct:   Optional[float]      = None
    document_urls:         Optional[Dict[str, str]] = None
    parent_project_id:     Optional[int]        = None
    belehnungswert_factor:   Optional[float]    = None
    estimated_down_pct:      Optional[float]    = None  # 80% LTV standard
    estimated_down_pct_kimv: Optional[float]    = None  # 90% LTV KIM-V program
    estimated_equity_eur:    Optional[int]      = None
    bank_score_confidence:   Optional[str]      = None  # "low" | "medium" | "high"
    betriebskosten_breakdown: Optional[Dict[str, Any]] = field(default_factory=dict)
    is_provisionsfrei:      Optional[bool]       = None
    bezirk_score:           Optional[float]      = None
    # --- Genossenschaft / co-op vertical (v1) ---
    is_genossenschaft:      Optional[bool]  = None
    bautraeger:             Optional[str]   = None   # "ÖVW" | "BWSG" | "Familienwohnbau" | ...
    allocation_model:       Optional[str]   = None   # 'first_come' | 'wohn_ticket'
    coop_source:            Optional[str]   = None   # 'bautraeger_direct' | 'willhaben'
    builder_url:            Optional[str]   = None   # builder's own reservation URL (mygewo → "Original-Anzeige")
    buyable:                Optional[bool]  = None   # mygewo "mit Kaufoption"; True = purchase-option unit (excluded from the rent-only feed)
    content_fingerprint_xsrc: Optional[str] = None   # source-independent dedup key
