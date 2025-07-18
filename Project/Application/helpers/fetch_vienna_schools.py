import requests
import json
import time

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:60];
area[\"name\"=\"Wien\"][admin_level=4];
(
  node[\"amenity\"=\"school\"](area);
  way[\"amenity\"=\"school\"](area);
  relation[\"amenity\"=\"school\"](area);
);
out center;
"""

def fetch_schools():
    response = requests.post(OVERPASS_URL, data=OVERPASS_QUERY, timeout=60)
    response.raise_for_status()
    data = response.json()
    schools = []
    for el in data.get('elements', []):
        lat = el.get('lat') or (el.get('center', {}).get('lat') if 'center' in el else None)
        lon = el.get('lon') or (el.get('center', {}).get('lon') if 'center' in el else None)
        tags = el.get('tags', {})
        name = tags.get('name')
        school_type = tags.get('isced:level') or tags.get('school:typ') or tags.get('operator:type') or tags.get('description') or "school"
        if lat and lon and name:
            schools.append({
                "name": name,
                "type": school_type,
                "lat": lat,
                "lon": lon
            })
    return schools

def save_schools(schools, filename="immo-scouter/vienna_schools.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(schools, f, indent=2, ensure_ascii=False) 