#!/usr/bin/env python3
"""
Buyer Profiles for Property Scoring
Different weight distributions for different buyer types
"""

from typing import Dict, Any

# Define all available buyer profiles
BUYER_PROFILES = {
    'default': {
        'name': 'Default Profile',
        'description': 'Balanced scoring for general property evaluation',
        'weights': {
            'price_per_m2': 0.20,
            'hwb_value': 0.05,
            'year_built': 0.15,
            'ubahn_walk_minutes': 0.15,
            'school_walk_minutes': 0.05,
            'rooms': 0.05,
            'balcony_terrace': 0.10,
            'floor_level': 0.05,
            'potential_growth_rating': 0.10,
            'renovation_needed_rating': 0.05,
            'area_m2': 0.05,
        }
    },
    
    'growing_family': {
        'name': 'Growing Family 👨‍👩‍👧‍👦',
        'description': 'Prioritizes space, safety, and convenience for children',
        'weights': {
            'school_walk_minutes': 0.20,
            'rooms': 0.20,
            'area_m2': 0.15,
            'balcony_terrace': 0.10,
            'price_per_m2': 0.10,
            'ubahn_walk_minutes': 0.10,
            'renovation_needed_rating': 0.05,
            'hwb_value': 0.05,
            'year_built': 0.05,
            'potential_growth_rating': 0.00,
            'floor_level': 0.00,
        }
    },
    
    'urban_professional': {
        'name': 'Urban Professional 💼',
        'description': 'Prioritizes location, lifestyle features, and modern comforts',
        'weights': {
            'ubahn_walk_minutes': 0.25,
            'balcony_terrace': 0.15,
            'year_built': 0.15,
            'price_per_m2': 0.15,
            'renovation_needed_rating': 0.10,
            'potential_growth_rating': 0.10,
            'floor_level': 0.05,
            'school_walk_minutes': 0.05,
            'rooms': 0.00,
            'area_m2': 0.00,
            'hwb_value': 0.00,
        }
    },
    
    'eco_conscious': {
        'name': 'Eco-Conscious Buyer 🌿',
        'description': 'Prioritizes sustainability, energy efficiency, and low carbon footprint',
        'weights': {
            'hwb_value': 0.25,
            'year_built': 0.20,
            'ubahn_walk_minutes': 0.15,
            'price_per_m2': 0.15,
            'balcony_terrace': 0.10,
            'renovation_needed_rating': 0.05,
            'potential_growth_rating': 0.05,
            'floor_level': 0.05,
            'rooms': 0.00,
            'school_walk_minutes': 0.00,
            'area_m2': 0.00,
        }
    },
    
    'diy_renovator': {
        'name': 'DIY Renovator / Flipper 🛠️',
        'description': 'Actively seeking properties to add value through renovation',
        'weights': {
            'price_per_m2': 0.30,
            'potential_growth_rating': 0.25,
            'renovation_needed_rating': 0.20,
            'area_m2': 0.10,
            'ubahn_walk_minutes': 0.10,
            'year_built': 0.05,
            'hwb_value': 0.00,
            'school_walk_minutes': 0.00,
            'rooms': 0.00,
            'balcony_terrace': 0.00,
            'floor_level': 0.00,
        }
    },
    
    'retiree': {
        'name': 'Retiree / Downsizer ☕',
        'description': 'Looking for comfort, accessibility, and peaceful living',
        'weights': {
            'floor_level': 0.25,
            'renovation_needed_rating': 0.20,
            'balcony_terrace': 0.15,
            'ubahn_walk_minutes': 0.15,
            'price_per_m2': 0.10,
            'hwb_value': 0.05,
            'area_m2': 0.05,
            'year_built': 0.05,
            'potential_growth_rating': 0.00,
            'school_walk_minutes': 0.00,
            'rooms': 0.00,
        }
    },
    
    'budget_buyer': {
        'name': 'First-Time Buyer on Strict Budget 💸',
        'description': 'Primary goal is to enter the property market at lowest cost',
        'weights': {
            'price_per_m2': 0.50,
            'ubahn_walk_minutes': 0.20,
            'hwb_value': 0.10,
            'renovation_needed_rating': 0.10,
            'area_m2': 0.05,
            'rooms': 0.05,
            'year_built': 0.00,
            'balcony_terrace': 0.00,
            'floor_level': 0.00,
            'potential_growth_rating': 0.00,
            'school_walk_minutes': 0.00,
        }
    }
}

def get_profile(profile_name: str) -> Dict[str, Any]:
    """
    Get a specific buyer profile by name.
    
    Args:
        profile_name: Name of the profile to retrieve
        
    Returns:
        Dict containing profile information and weights
        
    Raises:
        ValueError: If profile doesn't exist
    """
    if profile_name not in BUYER_PROFILES:
        available_profiles = list(BUYER_PROFILES.keys())
        raise ValueError(f"Profile '{profile_name}' not found. Available profiles: {available_profiles}")
    
    return BUYER_PROFILES[profile_name]

def list_profiles() -> Dict[str, str]:
    """
    List all available buyer profiles.
    
    Returns:
        Dict mapping profile keys to profile names
    """
    return {key: profile['name'] for key, profile in BUYER_PROFILES.items()}

def validate_profile_weights(weights: Dict[str, float]) -> bool:
    """
    Validate that profile weights sum to 1.0.
    
    Args:
        weights: Dictionary of criterion weights
        
    Returns:
        True if weights sum to 1.0, False otherwise
    """
    total_weight = sum(weights.values())
    return abs(total_weight - 1.0) < 0.001

def print_profile_summary(profile_name: str):
    """
    Print a summary of a buyer profile.
    
    Args:
        profile_name: Name of the profile to print
    """
    profile = get_profile(profile_name)
    
    print(f"\n📋 Buyer Profile: {profile['name']}")
    print(f"📝 Description: {profile['description']}")
    print(f"⚖️  Weight Distribution:")
    
    # Sort weights by value (highest first)
    sorted_weights = sorted(profile['weights'].items(), key=lambda x: x[1], reverse=True)
    
    for criterion, weight in sorted_weights:
        if weight > 0:
            percentage = weight * 100
            print(f"   • {criterion.replace('_', ' ').title()}: {percentage:.0f}%")
    
    total_weight = sum(profile['weights'].values())
    print(f"\n✅ Total Weight: {total_weight:.2f}")

def print_all_profiles():
    """
    Print a summary of all available buyer profiles.
    """
    print("🏠 Available Buyer Profiles:")
    print("=" * 50)
    
    for key, profile in BUYER_PROFILES.items():
        print(f"\n🔑 Key: '{key}'")
        print(f"📋 Name: {profile['name']}")
        print(f"📝 Description: {profile['description']}")
        
        # Show top 3 weights
        sorted_weights = sorted(profile['weights'].items(), key=lambda x: x[1], reverse=True)
        print("⚖️  Top Priorities:")
        for i, (criterion, weight) in enumerate(sorted_weights[:3]):
            if weight > 0:
                percentage = weight * 100
                print(f"   {i+1}. {criterion.replace('_', ' ').title()}: {percentage:.0f}%")

if __name__ == "__main__":
    # Test the module
    print_all_profiles()
    
    print("\n" + "=" * 50)
    print("Testing individual profile:")
    print_profile_summary('diy_renovator') 