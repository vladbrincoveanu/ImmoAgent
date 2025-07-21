#!/usr/bin/env python3
"""
Test script to demonstrate different buyer profiles and their scoring differences
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.buyer_profiles import print_all_profiles, print_profile_summary, get_profile
from Application.scoring import set_buyer_profile, score_apartment, get_current_profile
from Application.rating_calculator import calculate_all_ratings

def test_profile_comparison():
    """Test how different profiles score the same property"""
    print("🧪 Testing Buyer Profile Comparison")
    print("=" * 60)
    
    # Create a sample property that would be scored differently by different profiles
    sample_property = {
        'title': 'Mixed Property Example',
        'price_per_m2': 4000,          # Moderate price
        'hwb_value': 80,               # Moderate energy efficiency
        'year_built': 1985,            # Older building
        'ubahn_walk_minutes': 8,       # Moderate location
        'school_walk_minutes': 12,     # Moderate school proximity
        'rooms': 3,                    # Good number of rooms
        'area_m2': 75,                 # Moderate size
        'bezirk': '1120',              # Good district
        'energy_class': 'C',           # Moderate energy class
        'condition': 'Gut',            # Good condition
        'heating_type': 'Gas',         # Standard heating
        'special_features': ['Balkon'], # Has balcony
        'floor': 2                     # Second floor
    }
    
    # Calculate ratings
    ratings = calculate_all_ratings(sample_property)
    sample_property.update(ratings)
    
    print("📋 Sample Property:")
    for key, value in sample_property.items():
        print(f"   {key}: {value}")
    
    print(f"\n📊 Calculated Ratings:")
    for key, value in ratings.items():
        print(f"   {key}: {value}")
    
    # Test different profiles
    profiles_to_test = [
        'default',
        'growing_family', 
        'urban_professional',
        'eco_conscious',
        'diy_renovator',
        'retiree',
        'budget_buyer'
    ]
    
    print(f"\n🎯 Scoring Results by Profile:")
    print("=" * 60)
    
    results = []
    
    for profile_name in profiles_to_test:
        # Set the profile
        set_buyer_profile(profile_name)
        
        # Get profile info
        profile = get_profile(profile_name)
        
        # Calculate score
        score, breakdown = score_apartment(sample_property)
        
        results.append({
            'profile': profile_name,
            'name': profile['name'],
            'score': score,
            'breakdown': breakdown
        })
        
        print(f"\n📋 {profile['name']}")
        print(f"   Score: {score:.1f}")
        
        # Show top 3 contributing factors
        sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1]['weighted_score'], reverse=True)
        print("   Top 3 Factors:")
        for i, (criterion, details) in enumerate(sorted_breakdown[:3]):
            if details['weighted_score'] > 0:
                print(f"     {i+1}. {criterion.replace('_', ' ').title()}: {details['weighted_score']:.2f}")
    
    # Sort results by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n🏆 Final Ranking by Score:")
    print("=" * 40)
    for i, result in enumerate(results, 1):
        print(f"{i:2d}. {result['name']:<30} Score: {result['score']:5.1f}")
    
    return True

def test_profile_weights():
    """Test that all profile weights sum to 1.0"""
    print("\n\n🧪 Testing Profile Weight Validation")
    print("=" * 50)
    
    from Application.buyer_profiles import BUYER_PROFILES
    
    all_valid = True
    
    for profile_name, profile in BUYER_PROFILES.items():
        weights = profile['weights']
        total_weight = sum(weights.values())
        
        if abs(total_weight - 1.0) < 0.001:
            print(f"✅ {profile['name']}: {total_weight:.2f}")
        else:
            print(f"❌ {profile['name']}: {total_weight:.2f} (should be 1.00)")
            all_valid = False
    
    return all_valid

def main():
    """Run all tests"""
    print_all_profiles()
    
    success1 = test_profile_comparison()
    success2 = test_profile_weights()
    
    print("\n" + "=" * 60)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 