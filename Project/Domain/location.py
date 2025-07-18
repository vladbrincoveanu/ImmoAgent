import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class Coordinates:
    """Represents geographic coordinates with utility methods"""
    lat: float
    lon: float

    def __post_init__(self):
        """Validate coordinates after initialization"""
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Invalid latitude: {self.lat}. Must be between -90 and 90.")
        if not (-180 <= self.lon <= 180):
            raise ValueError(f"Invalid longitude: {self.lon}. Must be between -180 and 180.")

    def distance_to(self, other: 'Coordinates') -> float:
        """Calculate distance to another coordinate using Haversine formula (in meters)"""
        R = 6371000  # Earth's radius in meters

        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def walking_time_to(self, other: 'Coordinates', speed_m_per_min: float = 80.0) -> int:
        """Calculate walking time to another coordinate in minutes"""
        distance = self.distance_to(other)
        return int(round(distance / speed_m_per_min))

    def __str__(self) -> str:
        return f"Coordinates({self.lat:.4f}, {self.lon:.4f})"


@dataclass
class Amenity:
    """Represents a nearby amenity with distance information"""
    name: str
    distance_m: float
    type: str
    coordinates: Optional[Coordinates] = None

    @property
    def walking_time_minutes(self) -> int:
        """Calculate walking time in minutes (80m/min average)"""
        return int(round(self.distance_m / 80))

    def __str__(self) -> str:
        return f"{self.name} ({self.type}) - {self.walking_time_minutes}min walk"


@dataclass
class UBahnStation:
    """Represents a U-Bahn station with coordinates"""
    name: str
    coordinates: Coordinates
    district: str

    def distance_to(self, coords: Coordinates) -> float:
        """Calculate distance to given coordinates"""
        return self.coordinates.distance_to(coords)

    def walking_time_to(self, coords: Coordinates) -> int:
        """Calculate walking time to given coordinates"""
        return self.coordinates.walking_time_to(coords)
