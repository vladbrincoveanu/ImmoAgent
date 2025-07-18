import json
import os
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from Domain.location import Coordinates, UBahnStation

_config: Optional[Dict] = None
_project_root: Optional[str] = None

def get_project_root() -> str:
    """Finds the project root by looking for a sentinel file (e.g., README.md)."""
    global _project_root
    if _project_root:
        return _project_root

    path = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.exists(os.path.join(path, 'README.md')):
            _project_root = path
            return path
        parent_path = os.path.dirname(path)
        if parent_path == path:
            # We've reached the root of the filesystem
            # As a fallback, assume the parent of the current file's directory is the root
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = parent_path

def load_config() -> Dict:
    """Loads configuration from config.json at the project root."""
    global _config
    if _config is not None:
        return _config

    try:
        project_root = get_project_root()
        config_path = os.path.join(project_root, 'config.json')

        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_json = json.load(f)
                if isinstance(loaded_json, dict):
                    _config = loaded_json
                    print(f"✅ Loaded config from {config_path}")
                    return _config
        else:
            print(f"❌ Could not find config.json at {config_path}")

    except Exception as e:
        print(f"❌ Error loading config.json: {e}")

    # Fallback for old structure or errors
    print("⚠️  config.json not found in project root, trying legacy paths...")
    legacy_paths = ['config.json', 'immo-scouter/config.json']
    for path in legacy_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded_json = json.load(f)
                    if isinstance(loaded_json, dict):
                        _config = loaded_json
                        print(f"✅ Loaded config from legacy path: {path}")
                        return _config
            except Exception:
                continue

    raise FileNotFoundError("❌ No config file found!")


class DataLoader:
    """Utility class for loading JSON data files"""
    
    @staticmethod
    def get_data_path(filename: str) -> str:
        """Get the full path to a data file"""
        project_root = get_project_root()
        return os.path.join(project_root, 'data', filename)
    
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
        final_district = district if district else "1010"
        if not address or not district:
            return ViennaDistrictHelper.get_default_ubahn_time(final_district)
        
        # Check for transport keywords in address
        if any(keyword in address.lower() for keyword in ['bahnhof', 'station', 'metro', 'u-bahn']):
            return 3  # Very close to transport
        
        return ViennaDistrictHelper.get_default_ubahn_time(final_district)
    
    def find_nearest_station(self, coords: Coordinates, district: Optional[str] = None) -> Optional[Tuple[UBahnStation, float]]:
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
    final_district = district if district else "1010"
    return calculator.calculate_ubahn_proximity(address, final_district)


def get_default_ubahn_time(district: str) -> int:
    """Legacy function for backward compatibility"""
    return ViennaDistrictHelper.get_default_ubahn_time(district)


def estimate_betriebskosten(area_m2: float) -> Dict[str, float]:
    """
    Estimate monthly operating costs (Betriebskosten) for an apartment based on area.
    
    Austrian standard rates (excl. VAT):
    - Heizkosten: 1.22 EUR/m²
    - Reparaturrücklage: 1.29 EUR/m²  
    - Other core costs: 2.21 EUR/m²
    
    Returns dict with breakdown and total (incl. VAT)
    """
    if not area_m2 or area_m2 <= 0:
        return {
            'heizkosten': 0,
            'reparaturruecklage': 0, 
            'other_costs': 0,
            'subtotal_excl_vat': 0,
            'total_incl_vat': 0
        }
    
    # Austrian standard rates (excl. VAT)
    heizkosten_rate = 1.22  # EUR/m²
    reparatur_rate = 1.29   # EUR/m²
    other_rate = 2.21       # EUR/m²
    vat_rate = 0.0911       # 9.11% VAT
    
    # Calculate costs (excl. VAT)
    heizkosten = area_m2 * heizkosten_rate
    reparaturruecklage = area_m2 * reparatur_rate
    other_costs = area_m2 * other_rate
    
    # Subtotal (excl. VAT)
    subtotal_excl_vat = heizkosten + reparaturruecklage + other_costs
    
    # Total (incl. VAT)
    total_incl_vat = subtotal_excl_vat * (1 + vat_rate)
    
    return {
        'heizkosten': round(heizkosten, 2),
        'reparaturruecklage': round(reparaturruecklage, 2),
        'other_costs': round(other_costs, 2),
        'subtotal_excl_vat': round(subtotal_excl_vat, 2),
        'total_incl_vat': round(total_incl_vat, 2)
    }


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


def get_walking_times(district: str) -> tuple:
    """Get walking times for district (ubahn_minutes, school_minutes)"""
    # Default walking times for Vienna districts
    ubahn_times = {
        '1010': 3, '1020': 5, '1030': 6, '1040': 4, '1050': 5,
        '1060': 4, '1070': 3, '1080': 4, '1090': 5, '1100': 8,
        '1120': 6, '1130': 10, '1140': 8, '1150': 6, '1160': 7,
        '1190': 12, '1210': 10, '1220': 15, '1230': 12
    }
    
    school_times = {
        '1010': 5, '1020': 6, '1030': 7, '1040': 5, '1050': 6,
        '1060': 5, '1070': 4, '1080': 5, '1090': 6, '1100': 8,
        '1120': 7, '1130': 10, '1140': 8, '1150': 7, '1160': 8,
        '1190': 12, '1210': 10, '1220': 12, '1230': 10
    }
    
    return (
        ubahn_times.get(district, 10),
        school_times.get(district, 8)
    )
