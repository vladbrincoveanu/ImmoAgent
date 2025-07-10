#!/usr/bin/env python3
"""
Fetch all Vienna school locations and save as vienna_schools.json
- Uses Overpass API (OpenStreetMap) for all schools in Vienna
- Each entry: {"name": ..., "type": ..., "lat": ..., "lon": ...}
"""

import requests
import json
import time

# Overpass API query for all schools in Vienna
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Query: all nodes/ways/relations with amenity=school in Vienna
OVERPASS_QUERY = """
[out:json][timeout:60];
area["name"="Wien"][admin_level=4];
(
  node["amenity"="school"](area);
  way["amenity"="school"](area);
  relation["amenity"="school"](area);
);
out center;
"""

def fetch_schools():
    print("🔍 Fetching Vienna schools from Overpass API...")
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
    print(f"✅ Found {len(schools)} schools in Vienna.")
    return schools

def save_schools(schools, filename="immo-scouter/vienna_schools.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(schools, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved to {filename}")

def main():
    try:
        schools = fetch_schools()
        save_schools(schools)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()