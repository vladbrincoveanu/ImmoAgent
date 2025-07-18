#!/usr/bin/env python3
"""
Apartment Scoring System
Calculates weighted scores for apartments based on multiple criteria
"""

# --- Global Configuration for Apartment Scoring ---

# Define the minimum and maximum values for normalization for each criterion.
# These ranges should reflect what you consider "ideal" (score 100) and "acceptable worst" (score 0).
# Adjust these values based on your personal preferences and the current market reality.
NORMALIZATION_RANGES = {
    'price_per_m2': {'min_val': 3500, 'max_val': 8000, 'direction': 'lower_is_better'},
    'hwb_value': {'min_val': 20, 'max_val': 150, 'direction': 'lower_is_better'}, # HWB in kWh/m²/Jahr. 20 (A/A+) to 150 (F/G)
    'year_built': {'min_val': 1900, 'max_val': 2025, 'direction': 'higher_is_better'},
    'ubahn_walk_minutes': {'min_val': 2, 'max_val': 15, 'direction': 'lower_is_better'}, # minutes
    'school_walk_minutes': {'min_val': 3, 'max_val': 20, 'direction': 'lower_is_better'}, # minutes
    'rooms': {'min_val': 1, 'max_val': 5, 'direction': 'higher_is_better'}, # 1.0 to 5.0 rooms
    'area_m2': {'min_val': 70, 'max_val': 150, 'direction': 'higher_is_better'}, # square meters
    'balcony_terrace': {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'}, # 0 for No, 1 for Yes
    'floor_level': {'min_val': 0, 'max_val': 5, 'direction': 'higher_is_better'}, # 0 for Ground, 5 for 5th+
    'potential_growth_rating': {'min_val': 1, 'max_val': 5, 'direction': 'higher_is_better'}, # 1 (Low) to 5 (High)
    'renovation_needed_rating': {'min_val': 1, 'max_val': 5, 'direction': 'lower_is_better'}, # 1 (None) to 5 (Major)
}

# Define the weights for each criterion. Sum of weights should be 1.0 (or 100).
# Adjust these based on your personal priorities.
CRITERIA_WEIGHTS = {
    'price_per_m2': 0.20,
    'hwb_value': 0.15,
    'year_built': 0.10,
    'ubahn_walk_minutes': 0.15,
    'school_walk_minutes': 0.05,
    'rooms': 0.05,
    'balcony_terrace': 0.10,
    'floor_level': 0.05,
    'potential_growth_rating': 0.05,
    'renovation_needed_rating': 0.05,
    'area_m2': 0.05,
}

# Ensure weights sum to 1.0 for validation
def validate_weights():
    """Validate that weights sum to 1.0"""
    total_weight = sum(CRITERIA_WEIGHTS.values())
    if abs(total_weight - 1.0) > 0.001:
        raise ValueError(f"Weights must sum to 1.0, but sum to {total_weight}")

# Validate weights on import
validate_weights()

def normalize_value(criterion_name, actual_value):
    """
    Normalizes a given actual_value for a criterion to a score between 0 and 100.
    Capping values outside the defined range.
    """
    if criterion_name not in NORMALIZATION_RANGES:
        return 0.0

    config = NORMALIZATION_RANGES[criterion_name]
    min_val = config['min_val']
    max_val = config['max_val']
    direction = config['direction']

    if actual_value is None:
        return 0.0

    if direction == 'lower_is_better':
        if actual_value <= min_val:
            return 100.0
        elif actual_value >= max_val:
            return 0.0
        else:
            return 100.0 * (max_val - actual_value) / (max_val - min_val)
    elif direction == 'higher_is_better':
        if actual_value >= max_val:
            return 100.0
        elif actual_value <= min_val:
            return 0.0
        else:
            return 100.0 * (actual_value - min_val) / (max_val - min_val)
    else:
        return 0.0

def score_apartment(apartment_data):
    """
    Calculates the total weighted score for a single apartment.
    Returns the score and detailed breakdown.
    """
    apartment_id = apartment_data.get('_id', 'Unknown')
    weighted_scores_breakdown = {}
    total_score = 0.0

    for criterion, weight in CRITERIA_WEIGHTS.items():
        if criterion in apartment_data and apartment_data[criterion] is not None:
            actual_value = apartment_data[criterion]
            normalized_score = normalize_value(criterion, actual_value)
            weighted_score = normalized_score * weight
            
            weighted_scores_breakdown[criterion] = {
                'actual_value': actual_value,
                'normalized_score': round(normalized_score, 2),
                'weight': weight,
                'weighted_score': round(weighted_score, 2)
            }
            total_score += weighted_score
        else:
            weighted_scores_breakdown[criterion] = {
                'actual_value': None,
                'normalized_score': 0.0,
                'weight': weight,
                'weighted_score': 0.0
            }

    final_total_score = round(total_score, 1)
    
    return final_total_score, weighted_scores_breakdown

def score_apartment_simple(apartment_data):
    """
    Simple version that just returns the score without breakdown.
    """
    score, _ = score_apartment(apartment_data)
    return score

def print_apartment_score(apartment_data):
    """
    Prints a detailed breakdown of apartment scoring.
    """
    apartment_id = apartment_data.get('_id', 'Unknown')
    score, breakdown = score_apartment(apartment_data)
    
    print(f"\n--- Scoring Apartment: {apartment_id} ---")
    
    for criterion, details in breakdown.items():
        actual_value = details['actual_value']
        normalized_score = details['normalized_score']
        weight = details['weight']
        weighted_score = details['weighted_score']
        
        if actual_value is not None:
            print(f"{criterion.replace('_', ' ').title():<25}: Value={actual_value:<8} Normalized={normalized_score:>6.2f} Weight={weight:>5.2f} Weighted Score={weighted_score:>7.2f}")
        else:
            print(f"{criterion.replace('_', ' ').title():<25}: Missing data - Weighted Score={weighted_score:>7.2f}")
    
    print(f"{'TOTAL SCORE':<25}: {score:>60.2f}")
    
    return score, breakdown

def score_multiple_apartments(apartments_list):
    """
    Scores multiple apartments and returns them sorted by score.
    """
    apartment_results = []
    
    for apartment in apartments_list:
        score, breakdown = score_apartment(apartment)
        apartment_results.append({
            'apartment': apartment,
            'total_score': score, 
            'details': breakdown
        })

    # Sort apartments by total score (highest first)
    apartment_results.sort(key=lambda x: x['total_score'], reverse=True)
    
    return apartment_results

def print_apartment_ranking(apartments_list):
    """
    Prints a ranking of apartments by score.
    """
    results = score_multiple_apartments(apartments_list)
    
    print("\n--- Final Ranking of Apartments ---")
    for i, result in enumerate(results, 1):
        apartment = result['apartment']
        score = result['total_score']
        address = apartment.get('address', 'Unknown Address')
        price = apartment.get('price_total', 'N/A')
        
        print(f"{i:2d}. Score: {score:5.1f} | {address} | €{price:,}" if isinstance(price, (int, float)) else f"{i:2d}. Score: {score:5.1f} | {address} | {price}")
    
    return results

# Example usage and testing
if __name__ == "__main__":
    # Example apartment data
    APARTMENT_LISTINGS_EXAMPLE = [
        {
            'id': 'Apartment_A',
            'price_per_m2': 4000, # €/m²
            'hwb_value': 35, # kWh/m²/Jahr
            'year_built': 2010,
            'ubahn_walk_minutes': 4, # minutes
            'school_walk_minutes': 7, # minutes
            'rooms': 3.5,
            'area_m2': 85,
            'balcony_terrace': 1, # Yes
            'floor_level': 2, # 2nd floor
            'potential_growth_rating': 3, # Subjective 1-5
            'renovation_needed_rating': 2, # Subjective 1-5
        },
        {
            'id': 'Apartment_B',
            'price_per_m2': 5500,
            'hwb_value': 80,
            'year_built': 1950,
            'ubahn_walk_minutes': 2.5,
            'school_walk_minutes': 4,
            'rooms': 2.0,
            'area_m2': 65,
            'balcony_terrace': 0, # No
            'floor_level': 3,
            'potential_growth_rating': 4,
            'renovation_needed_rating': 3,
        },
    ]

    # Test individual scoring
    for apartment in APARTMENT_LISTINGS_EXAMPLE:
        print_apartment_score(apartment)

    # Test ranking
    print_apartment_ranking(APARTMENT_LISTINGS_EXAMPLE) 