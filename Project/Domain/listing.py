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
    source_enum: Optional[Source] = None
    score: Optional[float] = None
    potential_growth_rating: Optional[int] = None
    renovation_needed_rating: Optional[int] = None
    balcony_terrace: Optional[bool] = None
    floor_level: Optional[int] = None
