import requests
import math
import time
from typing import Dict, List, Optional, Tuple
from Domain.location import Coordinates, Amenity
from .utils import get_project_root, DataLoader

class ViennaGeocoder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Load Vienna U-Bahn stations from JSON data
        self.ubahn_stations = DataLoader.load_ubahn_stations()
        # Load Vienna schools from static JSON
        self.schools = DataLoader.load_vienna_schools()
        
        # Define major U-Bahn hubs for fallback calculations
        self.ubahn_hubs = {
            'Stephansplatz': Coordinates(48.2082, 16.3738),
            'Karlsplatz': Coordinates(48.2019, 16.3695),
            'Westbahnhof': Coordinates(48.1967, 16.3400),
            'Praterstern': Coordinates(48.2178, 16.3917),
            'Schottentor': Coordinates(48.2133, 16.3633),
            'Volkstheater': Coordinates(48.2033, 16.3583),
            'Rathaus': Coordinates(48.2100, 16.3583),
            'Heiligenstadt': Coordinates(48.2500, 16.3667),
            'Floridsdorf': Coordinates(48.2500, 16.4000),
            'Kagran': Coordinates(48.2333, 16.4500)
        }

    def find_nearest_school(self, coords: Coordinates) -> Optional[Tuple[float, dict]]:
        """Find the nearest school and return (distance_m, school_dict)"""
        if not coords or not self.schools:
            return None
        min_distance = float('inf')
        nearest_school = None
        for school in self.schools:
            try:
                school_coords = Coordinates(float(school['lat']), float(school['lon']))
                distance = self.calculate_distance(coords, school_coords)
                if distance < min_distance:
                    min_distance = distance
                    nearest_school = school
            except Exception:
                continue
        if nearest_school:
            return min_distance, nearest_school
        
        # Fallback to nearest hub if no specific school is found
        min_hub_distance = float('inf')
        for hub_coords in self.ubahn_hubs.values():
            distance = self.calculate_distance(coords, hub_coords)
            if distance < min_hub_distance:
                min_hub_distance = distance
        return min_hub_distance, {"name": "Nearest Hub"}


    def get_school_walk_minutes(self, coords: Coordinates) -> Optional[int]:
        """Return walking minutes to nearest school (distance/80m per min)"""
        result = self.find_nearest_school(coords)
        if result:
            distance_m, _ = result
            return int(round(distance_m / 80))
        return None

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

    def find_nearest_ubahn(self, coords: Coordinates, bezirk: str) -> Tuple[Optional[float], Optional[str]]:
        """Find the nearest U-Bahn station and return distance in meters and station name"""
        if not coords or not bezirk:
            return None, None
            
        stations = self.ubahn_stations.get(bezirk, [])
        if not stations:
            return None, None
            
        min_distance = float('inf')
        nearest_station = None
        
        for station in stations:
            distance = self.calculate_distance(coords, station.coordinates)
            if distance < min_distance:
                min_distance = distance
                nearest_station = station.name
        
        if nearest_station:
            return min_distance, nearest_station
        else:
            return None, None

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
    
    def get_walking_distance_to_nearest_ubahn(self, coords: Coordinates) -> Optional[int]:
        """Calculate actual walking distance to nearest U-Bahn station using Overpass API with improved fallback"""
        if not coords:
            return None
        
        try:
            # First attempt: Query for U-Bahn stations near the coordinates (2km radius)
            query = f"""
            [out:json][timeout:25];
            (
              node["railway"="station"]["station"~"subway|light_rail"]["network"~"U-Bahn Wien|Wiener Linien"](around:2000,{coords.lat},{coords.lon});
              node["public_transport"="station"]["subway"="yes"](around:2000,{coords.lat},{coords.lon});
              node["railway"="subway_entrance"](around:2000,{coords.lat},{coords.lon});
            );
            out;
            """
            
            response = self.session.post("https://overpass-api.de/api/interpreter", data=query, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            elements = data.get('elements', [])
            
            if elements:
                # Found stations via Overpass API - use the closest one
                min_distance = float('inf')
                closest_station = None
                
                for element in elements:
                    if 'lat' in element and 'lon' in element:
                        station_coords = Coordinates(element['lat'], element['lon'])
                        distance = self.calculate_distance(coords, station_coords)
                        
                        if distance < min_distance:
                            min_distance = distance
                            closest_station = element
                
                if closest_station:
                    walking_minutes = int(round(min_distance / 80))  # 80m/min average walking speed
                    station_name = closest_station.get('tags', {}).get('name', 'U-Bahn Station')
                    print(f"🚇 Closest U-Bahn: {station_name} ({walking_minutes} min walk)")
                    return walking_minutes
            
            # Fallback 1: No stations found in 2km radius, try static station coordinates by district
            print("🚇 No U-Bahn stations found via API, using district-based fallback...")
            district_result = self._get_ubahn_distance_by_district(coords)
            if district_result:
                return district_result
            
            # Fallback 2: Broader search radius (5km) with simplified query
            print("🚇 Trying broader search radius (5km)...")
            broader_result = self._get_ubahn_distance_broader_search(coords)
            if broader_result:
                return broader_result
            
            # Fallback 3: Geographic estimation based on Vienna layout
            print("🚇 Using geographic estimation fallback...")
            geographic_result = self._estimate_ubahn_distance_geographically(coords)
            return geographic_result
            
        except Exception as e:
            print(f"Error calculating U-Bahn distance: {e}")
            # Final fallback: Geographic estimation
            return self._estimate_ubahn_distance_geographically(coords)
    
    def _get_ubahn_distance_by_district(self, coords: Coordinates) -> Optional[int]:
        """Fallback 1: Use static station coordinates by district"""
        try:
            # Determine which district the coordinates are in
            district = self._determine_district_from_coords(coords)
            if not district:
                return None
            
            # Get stations for this district from our static data
            district_stations = self.ubahn_stations.get(district, [])
            if not district_stations:
                return None
            
            # Find closest station from static data
            min_distance = float('inf')
            closest_station_name = None
            
            for station in district_stations:
                distance = self.calculate_distance(coords, station.coordinates)
                if distance < min_distance:
                    min_distance = distance
                    closest_station_name = station.name
            
            if min_distance < float('inf'):
                walking_minutes = int(round(min_distance / 80))
                print(f"🚇 Closest U-Bahn (district {district}): {closest_station_name} ({walking_minutes} min walk)")
                return walking_minutes
            
            return None
            
        except Exception as e:
            print(f"Error in district-based fallback: {e}")
            return None
    
    def _get_ubahn_distance_broader_search(self, coords: Coordinates) -> Optional[int]:
        """Fallback 2: Try broader search radius with simplified query"""
        try:
            # Simplified query with 5km radius
            query = f"""
            [out:json][timeout:30];
            (
              node["railway"="station"](around:5000,{coords.lat},{coords.lon});
              node["public_transport"="station"](around:5000,{coords.lat},{coords.lon});
            );
            out;
            """
            
            response = self.session.post("https://overpass-api.de/api/interpreter", data=query, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            elements = data.get('elements', [])
            
            if elements:
                # Filter for likely U-Bahn stations and find closest
                min_distance = float('inf')
                closest_station = None
                
                for element in elements:
                    if 'lat' in element and 'lon' in element:
                        tags = element.get('tags', {})
                        name = tags.get('name', '').lower()
                        
                        # Filter for U-Bahn related keywords
                        if any(keyword in name for keyword in ['u-bahn', 'u1', 'u2', 'u3', 'u4', 'u6', 'metro', 'subway']):
                            station_coords = Coordinates(element['lat'], element['lon'])
                            distance = self.calculate_distance(coords, station_coords)
                            
                            if distance < min_distance:
                                min_distance = distance
                                closest_station = element
                
                if closest_station and min_distance < 8000:  # Max 8km reasonable for U-Bahn
                    walking_minutes = int(round(min_distance / 80))
                    station_name = closest_station.get('tags', {}).get('name', 'U-Bahn Station')
                    print(f"🚇 Closest U-Bahn (broad search): {station_name} ({walking_minutes} min walk)")
                    return walking_minutes
            
            return None
            
        except Exception as e:
            print(f"Error in broader search fallback: {e}")
            return None
    
    def _estimate_ubahn_distance_geographically(self, coords: Coordinates) -> int:
        """Estimate distance based on proximity to major U-Bahn hubs"""
        min_dist_to_hub = float('inf')
        for hub_coords in self.ubahn_hubs.values():
            distance = self.calculate_distance(coords, hub_coords)
            if distance < min_dist_to_hub:
                min_dist_to_hub = distance
        
        # Adjust walking time calculation for hubs
        return int(round(min_dist_to_hub / 75))

    def _determine_district_from_coords(self, coords: Coordinates) -> Optional[str]:
        """Determine district from coordinates using reverse geocoding"""
        try:
            # Rough district boundaries based on coordinates
            # This is a simplified mapping - in production you'd use proper district polygons
            lat, lon = coords.lat, coords.lon
            
            # Central districts (1010-1090)
            if 48.195 <= lat <= 48.220 and 16.355 <= lon <= 16.385:
                if lat >= 48.210:
                    return '1010' if lon <= 16.370 else '1020'
                else:
                    return '1040' if lon <= 16.370 else '1030'
            
            # Outer districts - simplified mapping
            district_map = [
                ('1060', 48.190, 48.210, 16.340, 16.360),
                ('1070', 48.200, 48.220, 16.340, 16.365),
                ('1080', 48.210, 48.230, 16.340, 16.365),
                ('1090', 48.215, 48.235, 16.355, 16.375),
                ('1100', 48.165, 48.195, 16.365, 16.405),
                ('1120', 48.170, 48.190, 16.320, 16.350),
                ('1130', 48.175, 48.205, 16.285, 16.325),
                ('1140', 48.190, 48.220, 16.300, 16.340),
                ('1150', 48.185, 48.205, 16.320, 16.350),
                ('1160', 48.205, 48.225, 16.310, 16.340),
                ('1190', 48.235, 48.280, 16.350, 16.390),
                ('1210', 48.240, 48.280, 16.390, 16.430),
                ('1220', 48.220, 48.260, 16.410, 16.500),
            ]
            
            for district, min_lat, max_lat, min_lon, max_lon in district_map:
                if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                    return district
            
            return None
            
        except Exception as e:
            print(f"Error determining district: {e}")
            return None
    
    def get_walking_distance_to_nearest_school(self, coords: Coordinates) -> Optional[int]:
        """Calculate actual walking distance to nearest school from Vienna schools JSON"""
        if not coords or not self.schools:
            return None
        
        try:
            # Find the closest school from our Vienna schools data
            min_distance = float('inf')
            closest_school = None
            
            for school in self.schools:
                try:
                    school_coords = Coordinates(float(school['lat']), float(school['lon']))
                    distance = self.calculate_distance(coords, school_coords)
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_school = school
                except Exception:
                    continue
            
            if closest_school:
                # Convert distance to walking time (average walking speed: 80m/min)
                walking_minutes = int(round(min_distance / 80))
                school_name = closest_school.get('name', 'School')
                print(f"🏫 Closest school: {school_name} ({walking_minutes} min walk)")
                return walking_minutes
            
            return None
            
        except Exception as e:
            print(f"Error calculating school distance: {e}")
            return None
    
    def calculate_walking_route(self, start_coords: Coordinates, end_coords: Coordinates) -> Optional[int]:
        """Calculate actual walking route using OpenRouteService API (free tier)"""
        try:
            # Using OpenRouteService free API for walking directions
            # Note: You can also use GraphHopper, MapBox, or other free routing APIs
            url = "https://api.openrouteservice.org/v2/directions/foot-walking"
            
            headers = {
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
                'Content-Type': 'application/json; charset=utf-8',
                # Note: For production, you should get a free API key from openrouteservice.org
                # 'Authorization': 'YOUR_FREE_API_KEY'
            }
            
            data = {
                "coordinates": [[start_coords.lon, start_coords.lat], [end_coords.lon, end_coords.lat]],
                "format": "json"
            }
            
            response = self.session.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                routes = result.get('routes', [])
                if routes:
                    # Get duration in seconds and convert to minutes
                    duration_seconds = routes[0]['summary']['duration']
                    walking_minutes = int(round(duration_seconds / 60))
                    return walking_minutes
            
            # Fallback to straight-line distance calculation
            distance_m = self.calculate_distance(start_coords, end_coords)
            walking_minutes = int(round(distance_m / 80))  # 80m/min average walking speed
            return walking_minutes
            
        except Exception as e:
            print(f"Error calculating walking route: {e}")
            # Fallback to straight-line distance calculation
            distance_m = self.calculate_distance(start_coords, end_coords)
            walking_minutes = int(round(distance_m / 80))
            return walking_minutes 