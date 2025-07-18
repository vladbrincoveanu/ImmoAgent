#!/usr/bin/env python3
"""
Test script to verify district extraction logic
"""

import re

def test_district_extraction():
    """Test district extraction from different address formats"""
    
    # Test addresses
    test_addresses = [
        "Wien, 22. Bezirk, Donaustadt",  # Your format
        "1220 Wien",  # 4-digit format
        "Neubaugasse 12, 1070 Wien",  # Street + 4-digit
        "Stephansplatz 1, 1010 Wien",  # Another 4-digit
        "Invalid address format",  # Should fail
        "Wien, 1. Bezirk, Innere Stadt",  # 1. Bezirk format
        "Wien, 15. Bezirk, Rudolfsheim-Fünfhaus"  # 15. Bezirk format
    ]
    
    print("🧪 Testing District Extraction Logic")
    print("=" * 50)
    
    for i, address in enumerate(test_addresses, 1):
        print(f"\n{i}. Testing: '{address}'")
        
        # Extract district using the same logic as in scrape.py
        district = None
        
        # Try format: "1220 Wien" (4-digit code)
        district_match = re.search(r'(\d{4})\s*Wien', address)
        if district_match:
            district = district_match.group(1)
            print(f"   ✅ Found 4-digit format: {district}")
        else:
            # Try format: "22. Bezirk" (2-digit with dot)
            bezirk_match = re.search(r'(\d+)\.\s*Bezirk', address)
            if bezirk_match:
                district_num = bezirk_match.group(1)
                # Convert 2-digit to 4-digit format
                district_map = {
                    '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
                    '6': '1060', '7': '1070', '8': '1080', '9': '1090', '10': '1100',
                    '11': '1110', '12': '1120', '13': '1130', '14': '1140', '15': '1150',
                    '16': '1160', '17': '1170', '18': '1180', '19': '1190', '20': '1200',
                    '21': '1210', '22': '1220', '23': '1230'
                }
                district = district_map.get(district_num)
                print(f"   ✅ Found Bezirk format: {district_num}. Bezirk → {district}")
            else:
                print(f"   ❌ No district found")
        
        if district:
            # Test walking times
            ubahn_times = {
                '1010': 3, '1020': 5, '1030': 6, '1040': 4, '1050': 5,
                '1060': 4, '1070': 3, '1080': 4, '1090': 5, '1100': 8,
                '1120': 6, '1130': 10, '1140': 8, '1150': 6, '1160': 7,
                '1190': 12, '1210': 10, '1220': 15
            }
            
            school_times = {
                '1010': 5, '1020': 6, '1030': 7, '1040': 5, '1050': 6,
                '1060': 5, '1070': 4, '1080': 5, '1090': 6, '1100': 8,
                '1120': 7, '1130': 10, '1140': 8, '1150': 7, '1160': 8,
                '1190': 12, '1210': 10, '1220': 12
            }
            
            ubahn_min = ubahn_times.get(district, 10)
            school_min = school_times.get(district, 8)
            
            print(f"   🚇 U-Bahn: {ubahn_min} min")
            print(f"   🏫 School: {school_min} min")
        else:
            print(f"   🚇 U-Bahn: N/A")
            print(f"   🏫 School: N/A")

if __name__ == "__main__":
    test_district_extraction() 