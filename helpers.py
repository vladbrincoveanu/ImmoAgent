from typing import Optional


def calculate_ubahn_proximity(address: str, bezirk: str) -> Optional[int]:
    """Calculate walking distance to nearest U-Bahn station"""
    if not address or not bezirk:
        return get_default_ubahn_time(bezirk)
    
    # Vienna U-Bahn stations by district
    ubahn_stations = {
        '1010': ['Stephansplatz', 'Karlsplatz', 'Herrengasse'],
        '1020': ['Taborstraße', 'Nestroyplatz', 'Praterstern'],
        '1030': ['Landstraße', 'Rochusgasse', 'Kardinal-Nagl-Platz'],
        '1040': ['Karlsplatz', 'Kettenbrückengasse', 'Pilgramgasse'],
        '1050': ['Kettenbrückengasse', 'Margaretengürtel', 'Pilgramgasse'],
        '1060': ['Westbahnhof', 'Burggasse-Stadthalle', 'Gumpendorfer Straße'],
        '1070': ['Volkstheater', 'Neubaugasse', 'Burggasse-Stadthalle'],
        '1080': ['Rathaus', 'Josefstädter Straße', 'Alser Straße'],
        '1090': ['Schottentor', 'Rossauer Lände', 'Friedensbrücke'],
        '1100': ['Keplerplatz', 'Südtiroler Platz', 'Troststraße'],
        '1120': ['Längenfeldgasse', 'Meidling Hauptstraße', 'Niederhofstraße'],
        '1130': ['Hietzing', 'Unter St. Veit', 'Ober St. Veit'],
        '1140': ['Penzing', 'Braunschweiggasse', 'Hütteldorfer Straße'],
        '1150': ['Westbahnhof', 'Schweglerstraße', 'Johnstraße'],
        '1160': ['Ottakring', 'Kendlerstraße', 'Thaliastraße'],
        '1190': ['Heiligenstadt', 'Spittelau', 'Nußdorfer Straße'],
        '1210': ['Floridsdorf', 'Neue Donau', 'Handelskai'],
        '1220': ['Kagran', 'Kagraner Platz', 'Rennbahnweg']
    }
    
    # Get stations for the district
    stations = ubahn_stations.get(bezirk, [])
    if not stations:
        return get_default_ubahn_time(bezirk)
    
    # For now, use heuristic based on district and address keywords
    # In production, you'd use Google Maps API or similar
    if any(keyword in address.lower() for keyword in ['bahnhof', 'station', 'metro', 'u-bahn']):
        return 3  # Very close to transport
    
    return get_default_ubahn_time(bezirk)

def get_default_ubahn_time(bezirk: str) -> int:
    """Default U-Bahn walking times by district"""
    default_times = {
        '1010': 5, '1020': 8, '1030': 10, '1040': 7, '1050': 9,
        '1060': 6, '1070': 5, '1080': 8, '1090': 7, '1100': 12,
        '1120': 10, '1130': 15, '1140': 12, '1150': 8, '1160': 10,
        '1190': 15, '1210': 12, '1220': 18
    }
    return default_times.get(bezirk, 15)
