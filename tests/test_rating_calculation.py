#!/usr/bin/env python3
"""
Test script to verify rating calculation and scoring system
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.rating_calculator import calculate_all_ratings, calculate_potential_growth_rating, calculate_renovation_needed_rating
from Application.scoring import score_apartment, print_apartment_score

def test_rating_calculation():
    """Test the rating calculation functions"""
    print("🧪 Testing Rating Calculation System")
    print("=" * 50)
    
    # Test case 1: Modern apartment in good district
    modern_apartment = {
        'title': 'Neue Wohnung mit Balkon',
        'year_built': 2020,
        'bezirk': '1020',
        'energy_class': 'A',
        'condition': 'Erstbezug',
        'ubahn_walk_minutes': 3,
        'heating_type': 'Fernwärme',
        'special_features': ['Balkon', 'Aufzug'],
        'floor': 2
    }
    
    # Test case 2: Old apartment in outer district
    old_apartment = {
        'title': 'Altbau Wohnung',
        'year_built': 1950,
        'bezirk': '1210',
        'energy_class': 'F',
        'condition': 'Sanierungsbedürftig',
        'ubahn_walk_minutes': 12,
        'heating_type': 'Ölheizung',
        'special_features': [],
        'floor': 1
    }
    
    # Test case 3: Medium apartment
    medium_apartment = {
        'title': 'Standard Wohnung',
        'year_built': 1995,
        'bezirk': '1120',
        'energy_class': 'C',
        'condition': 'Gut',
        'ubahn_walk_minutes': 8,
        'heating_type': 'Gas',
        'special_features': ['Terrasse'],
        'floor': 3
    }
    
    test_cases = [
        ("Modern Apartment", modern_apartment),
        ("Old Apartment", old_apartment),
        ("Medium Apartment", medium_apartment)
    ]
    
    for name, apartment in test_cases:
        print(f"\n📊 Testing {name}:")
        print("-" * 30)
        
        # Calculate ratings
        ratings = calculate_all_ratings(apartment)
        
        print(f"Potential Growth Rating: {ratings['potential_growth_rating']}/5")
        print(f"Renovation Needed Rating: {ratings['renovation_needed_rating']}/5")
        print(f"Balcony/Terrace: {ratings['balcony_terrace']}")
        print(f"Floor Level: {ratings['floor_level']}")
        
        # Add ratings to apartment data
        apartment.update(ratings)
        
        # Add some required fields for scoring
        apartment.update({
            'price_per_m2': 5000,
            'hwb_value': 50,
            'rooms': 3,
            'area_m2': 80
        })
        
        # Calculate score
        score, breakdown = score_apartment(apartment)
        print(f"Total Score: {score:.1f}")
        
        # Show detailed breakdown
        print("\nDetailed Score Breakdown:")
        for criterion, details in breakdown.items():
            if details['actual_value'] is not None:
                print(f"  {criterion}: {details['actual_value']} → {details['normalized_score']:.1f} × {details['weight']:.2f} = {details['weighted_score']:.2f}")
    
    return True

def test_scoring_with_ratings():
    """Test the complete scoring system with calculated ratings"""
    print("\n\n🧪 Testing Complete Scoring System")
    print("=" * 50)
    
    # Create a realistic apartment listing
    apartment = {
        'title': 'Traumwohnung in 1020',
        'price_per_m2': 4500,
        'hwb_value': 35,
        'year_built': 2018,
        'ubahn_walk_minutes': 4,
        'school_walk_minutes': 6,
        'rooms': 3.5,
        'area_m2': 85,
        'bezirk': '1020',
        'energy_class': 'A',
        'condition': 'Erstbezug',
        'heating_type': 'Fernwärme',
        'special_features': ['Balkon', 'Aufzug', 'Keller'],
        'floor': 2
    }
    
    print("📋 Original Apartment Data:")
    for key, value in apartment.items():
        print(f"  {key}: {value}")
    
    # Calculate ratings
    ratings = calculate_all_ratings(apartment)
    apartment.update(ratings)
    
    print(f"\n📊 Calculated Ratings:")
    for key, value in ratings.items():
        print(f"  {key}: {value}")
    
    # Calculate score
    print(f"\n🎯 Final Score Calculation:")
    score, breakdown = score_apartment(apartment)
    
    print_apartment_score(apartment)
    
    return True

def main():
    """Run all tests"""
    success1 = test_rating_calculation()
    success2 = test_scoring_with_ratings()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 