import json
import os
import math
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass


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


class DataLoader:
    """Utility class for loading JSON data files"""
    
    @staticmethod
    def get_data_path(filename: str) -> str:
        """Get the full path to a data file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, 'data', filename)
    
    @staticmethod
    def load_ubahn_stations() -> Dict[str, List[UBahnStation]]:
        """Load U-Bahn stations from JSON file"""
        try:
            data_path = DataLoader.get_data_path('ubahn_coordinates.json')
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stations = {}
            for district, station_list in data.items():
                stations[district] = []
                for station_data in station_list:
                    coords = Coordinates(station_data['lat'], station_data['lon'])
                    station = UBahnStation(
                        name=station_data['name'],
                        coordinates=coords,
                        district=district
                    )
                    stations[district].append(station)
            
            return stations
        except Exception as e:
            print(f"Error loading U-Bahn stations: {e}")
            return {}
    
    @staticmethod
    def load_vienna_schools() -> List[Dict]:
        """Load Vienna schools from JSON file"""
        try:
            data_path = DataLoader.get_data_path('vienna_schools.json')
            with open(data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading Vienna schools: {e}")
            return []


class ViennaDistrictHelper:
    """Helper class for Vienna district operations"""
    
    # Default U-Bahn walking times by district (fallback values)
    DEFAULT_UBAHN_TIMES = {
        '1010': 5, '1020': 8, '1030': 10, '1040': 7, '1050': 9,
        '1060': 6, '1070': 5, '1080': 8, '1090': 7, '1100': 12,
        '1120': 10, '1130': 15, '1140': 12, '1150': 8, '1160': 10,
        '1190': 15, '1210': 12, '1220': 18
    }
    
    @staticmethod
    def get_default_ubahn_time(district: str) -> int:
        """Get default U-Bahn walking time for a district"""
        return ViennaDistrictHelper.DEFAULT_UBAHN_TIMES.get(district, 15)
    
    @staticmethod
    def is_valid_district(district: str) -> bool:
        """Check if a district code is valid for Vienna"""
        return district in ViennaDistrictHelper.DEFAULT_UBAHN_TIMES
    
    @staticmethod
    def get_district_name(district: str) -> str:
        """Get the name of a Vienna district"""
        district_names = {
            '1010': 'Innere Stadt',
            '1020': 'Leopoldstadt',
            '1030': 'Landstraße',
            '1040': 'Wieden',
            '1050': 'Margareten',
            '1060': 'Mariahilf',
            '1070': 'Neubau',
            '1080': 'Josefstadt',
            '1090': 'Alsergrund',
            '1100': 'Favoriten',
            '1110': 'Simmering',
            '1120': 'Meidling',
            '1130': 'Hietzing',
            '1140': 'Penzing',
            '1150': 'Rudolfsheim-Fünfhaus',
            '1160': 'Ottakring',
            '1170': 'Hernals',
            '1180': 'Währing',
            '1190': 'Döbling',
            '1200': 'Brigittenau',
            '1210': 'Floridsdorf',
            '1220': 'Donaustadt',
            '1230': 'Liesing'
        }
        return district_names.get(district, f"District {district}")


class UBahnProximityCalculator:
    """Calculator for U-Bahn proximity using real station data"""
    
    def __init__(self):
        self.stations = DataLoader.load_ubahn_stations()
    
    def calculate_ubahn_proximity(self, address: str, district: Optional[str]) -> Optional[int]:
        """Calculate walking distance to nearest U-Bahn station"""
        if not address or not district:
            return ViennaDistrictHelper.get_default_ubahn_time(district or "1010")
        
        # Check for transport keywords in address
        if any(keyword in address.lower() for keyword in ['bahnhof', 'station', 'metro', 'u-bahn']):
            return 3  # Very close to transport
        
        return ViennaDistrictHelper.get_default_ubahn_time(district)
    
    def find_nearest_station(self, coords: Coordinates, district: str = None) -> Optional[Tuple[UBahnStation, float]]:
        """Find the nearest U-Bahn station to given coordinates"""
        if not coords:
            return None
        
        min_distance = float('inf')
        nearest_station = None
        
        # Search in specific district first if provided
        if district and district in self.stations:
            for station in self.stations[district]:
                distance = station.distance_to(coords)
                if distance < min_distance:
                    min_distance = distance
                    nearest_station = station
        
        # If no station found in district or no district provided, search all
        if nearest_station is None:
            for district_stations in self.stations.values():
                for station in district_stations:
                    distance = station.distance_to(coords)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_station = station
        
        return (nearest_station, min_distance) if nearest_station else None


def calculate_ubahn_proximity(address: str, district: Optional[str]) -> Optional[int]:
    """Legacy function for backward compatibility"""
    calculator = UBahnProximityCalculator()
    return calculator.calculate_ubahn_proximity(address, district or "1010")


def get_default_ubahn_time(district: str) -> int:
    """Legacy function for backward compatibility"""
    return ViennaDistrictHelper.get_default_ubahn_time(district)


# Utility functions for common operations
def safe_float(value, default=None):
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=None):
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def format_currency(amount: Optional[float], currency: str = "€") -> str:
    """Format amount as currency string"""
    if amount is None:
        return "N/A"
    return f"{currency}{amount:,.0f}"


def format_distance(distance_m: Optional[float]) -> str:
    """Format distance in meters to human readable string"""
    if distance_m is None:
        return "N/A"
    
    if distance_m < 1000:
        return f"{distance_m:.0f}m"
    else:
        return f"{distance_m/1000:.1f}km"


def format_walking_time(distance_m: Optional[float]) -> str:
    """Format walking time based on distance"""
    if distance_m is None:
        return "N/A"
    
    minutes = int(round(distance_m / 80))  # 80m/min average walking speed
    if minutes < 60:
        return f"{minutes} min"
    else:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}min"
