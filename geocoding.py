import requests
import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class Coordinates:
    lat: float
    lon: float

@dataclass
class Amenity:
    name: str
    distance_m: float
    type: str

class ViennaGeocoder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Vienna U-Bahn stations with coordinates (major stations)
        self.ubahn_stations = {
            '1010': [  # City center
                Coordinates(48.2082, 16.3738),  # Stephansplatz
                Coordinates(48.2019, 16.3695),  # Karlsplatz
                Coordinates(48.2104, 16.3665),  # Herrengasse
            ],
            '1020': [  # Prater area
                Coordinates(48.2175, 16.3958),  # Taborstraße
                Coordinates(48.2189, 16.3975),  # Nestroyplatz
                Coordinates(48.2178, 16.3917),  # Praterstern
            ],
            '1030': [  # Landstraße
                Coordinates(48.2075, 16.3833),  # Landstraße
                Coordinates(48.2047, 16.3867),  # Rochusgasse
                Coordinates(48.2019, 16.3892),  # Kardinal-Nagl-Platz
            ],
            '1040': [  # Wieden
                Coordinates(48.2019, 16.3695),  # Karlsplatz
                Coordinates(48.1958, 16.3650),  # Kettenbrückengasse
                Coordinates(48.1908, 16.3600),  # Pilgramgasse
            ],
            '1050': [  # Margareten
                Coordinates(48.1958, 16.3650),  # Kettenbrückengasse
                Coordinates(48.1883, 16.3583),  # Margaretengürtel
                Coordinates(48.1908, 16.3600),  # Pilgramgasse
            ],
            '1060': [  # Mariahilf
                Coordinates(48.1967, 16.3400),  # Westbahnhof
                Coordinates(48.1983, 16.3450),  # Burggasse-Stadthalle
                Coordinates(48.1950, 16.3500),  # Gumpendorfer Straße
            ],
            '1070': [  # Neubau
                Coordinates(48.2033, 16.3583),  # Volkstheater
                Coordinates(48.2017, 16.3533),  # Neubaugasse
                Coordinates(48.1983, 16.3450),  # Burggasse-Stadthalle
            ],
            '1080': [  # Josefstadt
                Coordinates(48.2100, 16.3583),  # Rathaus
                Coordinates(48.2083, 16.3533),  # Josefstädter Straße
                Coordinates(48.2133, 16.3500),  # Alser Straße
            ],
            '1090': [  # Alsergrund
                Coordinates(48.2133, 16.3633),  # Schottentor
                Coordinates(48.2250, 16.3667),  # Rossauer Lände
                Coordinates(48.2283, 16.3700),  # Friedensbrücke
            ],
            '1100': [  # Favoriten
                Coordinates(48.1750, 16.3750),  # Keplerplatz
                Coordinates(48.1867, 16.4200),  # Südtiroler Platz
                Coordinates(48.1700, 16.3800),  # Troststraße
            ],
            '1120': [  # Meidling
                Coordinates(48.1750, 16.3300),  # Längenfeldgasse
                Coordinates(48.1750, 16.3400),  # Meidling Hauptstraße
                Coordinates(48.1700, 16.3350),  # Niederhofstraße
            ],
            '1130': [  # Hietzing
                Coordinates(48.1867, 16.3000),  # Hietzing
                Coordinates(48.1900, 16.2900),  # Unter St. Veit
                Coordinates(48.1950, 16.2850),  # Ober St. Veit
            ],
            '1140': [  # Penzing
                Coordinates(48.1967, 16.3100),  # Penzing
                Coordinates(48.2000, 16.3050),  # Braunschweiggasse
                Coordinates(48.2033, 16.3000),  # Hütteldorfer Straße
            ],
            '1150': [  # Rudolfsheim
                Coordinates(48.1967, 16.3400),  # Westbahnhof
                Coordinates(48.1950, 16.3350),  # Schweglerstraße
                Coordinates(48.1933, 16.3300),  # Johnstraße
            ],
            '1160': [  # Ottakring
                Coordinates(48.2100, 16.3200),  # Ottakring
                Coordinates(48.2083, 16.3150),  # Kendlerstraße
                Coordinates(48.2067, 16.3100),  # Thaliastraße
            ],
            '1190': [  # Döbling
                Coordinates(48.2500, 16.3667),  # Heiligenstadt
                Coordinates(48.2333, 16.3700),  # Spittelau
                Coordinates(48.2300, 16.3600),  # Nußdorfer Straße
            ],
            '1210': [  # Floridsdorf
                Coordinates(48.2500, 16.4000),  # Floridsdorf
                Coordinates(48.2333, 16.4200),  # Neue Donau
                Coordinates(48.2300, 16.4100),  # Handelskai
            ],
            '1220': [  # Donaustadt
                Coordinates(48.2333, 16.4500),  # Kagran
                Coordinates(48.2300, 16.4450),  # Kagraner Platz
                Coordinates(48.2250, 16.4400),  # Rennbahnweg
            ]
        }

    def geocode_address(self, address: str) -> Optional[Coordinates]:
        """Geocode an address using OpenStreetMap Nominatim"""
        if not address:
            return None
            
        try:
            # Add Vienna to the address if not present
            if 'Wien' not in address:
                address = f"{address}, Wien, Austria"
            
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'at'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                return Coordinates(lat, lon)
            
            return None
            
        except Exception as e:
            print(f"Error geocoding address '{address}': {e}")
            return None

    def calculate_distance(self, coord1: Coordinates, coord2: Coordinates) -> float:
        """Calculate distance between two coordinates using Haversine formula (in meters)"""
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1 = math.radians(coord1.lat), math.radians(coord1.lon)
        lat2, lon2 = math.radians(coord2.lat), math.radians(coord2.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def find_nearest_ubahn(self, coords: Coordinates, bezirk: str) -> Tuple[float, str]:
        """Find the nearest U-Bahn station and return distance in meters and station name"""
        if not coords or not bezirk:
            return None, None
            
        stations = self.ubahn_stations.get(bezirk, [])
        if not stations:
            return None, None
            
        min_distance = float('inf')
        nearest_station = None
        
        for station in stations:
            distance = self.calculate_distance(coords, station)
            if distance < min_distance:
                min_distance = distance
                nearest_station = f"U-Bahn {bezirk}"
        
        return min_distance, nearest_station

    def find_nearby_amenities(self, coords: Coordinates, radius_m: int = 1000) -> List[Amenity]:
        """Find nearby amenities using Overpass API"""
        if not coords:
            return []
            
        amenities = []
        
        # Define amenity types to search for
        amenity_types = {
            'shop': ['supermarket', 'convenience', 'mall'],
            'education': ['kindergarten', 'school', 'university'],
            'healthcare': ['pharmacy', 'hospital'],
            'transport': ['bus_station', 'tram_stop']
        }
        
        for category, types in amenity_types.items():
            for amenity_type in types:
                try:
                    # Overpass API query
                    query = f"""
                    [out:json][timeout:25];
                    (
                      node["amenity"="{amenity_type}"](around:{radius_m},{coords.lat},{coords.lon});
                      way["amenity"="{amenity_type}"](around:{radius_m},{coords.lat},{coords.lon});
                      relation["amenity"="{amenity_type}"](around:{radius_m},{coords.lat},{coords.lon});
                    );
                    out center;
                    """
                    
                    url = "https://overpass-api.de/api/interpreter"
                    response = self.session.post(url, data=query, timeout=15)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    for element in data.get('elements', []):
                        if 'lat' in element and 'lon' in element:
                            amenity_coords = Coordinates(element['lat'], element['lon'])
                            distance = self.calculate_distance(coords, amenity_coords)
                            
                            name = element.get('tags', {}).get('name', f"{amenity_type.title()}")
                            amenities.append(Amenity(
                                name=name,
                                distance_m=distance,
                                type=category
                            ))
                    
                    # Rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error finding {amenity_type} amenities: {e}")
                    continue
        
        # Sort by distance and return top results
        amenities.sort(key=lambda x: x.distance_m)
        return amenities[:10]  # Return top 10 closest amenities

    def get_amenity_summary(self, amenities: List[Amenity]) -> Dict[str, Dict]:
        """Summarize amenities by category"""
        summary = {
            'shopping': {'count': 0, 'closest': None},
            'education': {'count': 0, 'closest': None},
            'healthcare': {'count': 0, 'closest': None},
            'transport': {'count': 0, 'closest': None}
        }
        
        for amenity in amenities:
            category = amenity.type
            if category in summary:
                summary[category]['count'] += 1
                if summary[category]['closest'] is None or amenity.distance_m < summary[category]['closest'].distance_m:
                    summary[category]['closest'] = amenity
        
        return summary 