#!/usr/bin/env python3
"""
Rating Calculator for Property Analysis
Calculates potential_growth_rating and renovation_needed_rating based on property characteristics
"""

from typing import Dict, Any, Optional
import logging

def calculate_potential_growth_rating(listing: Dict[str, Any]) -> int:
    """
    Calculate potential growth rating (1-5) based on property characteristics.
    
    Factors considered:
    - Year built (newer = higher potential)
    - District (better districts = higher potential)
    - Energy efficiency (better = higher potential)
    - Condition (better = higher potential)
    - Infrastructure proximity (better = higher potential)
    
    Returns:
        int: Rating from 1 (Low) to 5 (High)
    """
    try:
        score = 0
        
        # Year built factor (0-2 points)
        year_built = listing.get('year_built')
        if year_built:
            if year_built >= 2020:
                score += 2
            elif year_built >= 2010:
                score += 1.5
            elif year_built >= 2000:
                score += 1
            elif year_built >= 1990:
                score += 0.5
            # Older buildings get 0 points
        
        # District factor (0-1 point)
        bezirk = listing.get('bezirk')
        if bezirk:
            # Premium districts
            premium_districts = ['1010', '1020', '1030', '1040', '1050', '1060', '1070', '1080', '1090']
            if bezirk in premium_districts:
                score += 1
            # Good districts
            good_districts = ['1100', '1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190', '1200', '1210', '1220', '1230']
            if bezirk in good_districts:
                score += 0.5
        
        # Energy efficiency factor (0-1 point)
        energy_class = listing.get('energy_class')
        hwb_value = listing.get('hwb_value')
        
        if energy_class:
            if energy_class in ['A+', 'A']:
                score += 1
            elif energy_class in ['B', 'B+']:
                score += 0.7
            elif energy_class in ['C', 'C+']:
                score += 0.4
            elif energy_class in ['D', 'D+']:
                score += 0.2
        elif hwb_value:
            if hwb_value <= 25:
                score += 1
            elif hwb_value <= 50:
                score += 0.7
            elif hwb_value <= 100:
                score += 0.4
            elif hwb_value <= 150:
                score += 0.2
        
        # Condition factor (0-0.5 points)
        condition = listing.get('condition', '').lower()
        if 'erstbezug' in condition or 'neu' in condition or 'neubau' in condition:
            score += 0.5
        elif 'gut' in condition or 'sehr gut' in condition:
            score += 0.3
        elif 'renoviert' in condition or 'saniert' in condition:
            score += 0.2
        
        # Infrastructure proximity factor (0-0.5 points)
        ubahn_minutes = listing.get('ubahn_walk_minutes')
        if ubahn_minutes and ubahn_minutes <= 5:
            score += 0.5
        elif ubahn_minutes and ubahn_minutes <= 10:
            score += 0.3
        elif ubahn_minutes and ubahn_minutes <= 15:
            score += 0.1
        
        # Convert to 1-5 scale
        if score >= 4.5:
            return 5
        elif score >= 3.5:
            return 4
        elif score >= 2.5:
            return 3
        elif score >= 1.5:
            return 2
        else:
            return 1
            
    except Exception as e:
        logging.warning(f"Error calculating potential growth rating: {e}")
        return 3  # Default to medium

def calculate_renovation_needed_rating(listing: Dict[str, Any]) -> int:
    """
    Calculate renovation needed rating (1-5) based on property characteristics.
    
    Factors considered:
    - Year built (older = more renovation needed)
    - Energy efficiency (worse = more renovation needed)
    - Condition (worse = more renovation needed)
    - Heating type (old = more renovation needed)
    
    Returns:
        int: Rating from 1 (None needed) to 5 (Major renovation needed)
    """
    try:
        score = 0
        
        # Year built factor (0-2 points)
        year_built = listing.get('year_built')
        if year_built:
            if year_built < 1960:
                score += 2
            elif year_built < 1980:
                score += 1.5
            elif year_built < 1990:
                score += 1
            elif year_built < 2000:
                score += 0.5
            # Newer buildings get 0 points
        
        # Energy efficiency factor (0-1.5 points)
        energy_class = listing.get('energy_class')
        hwb_value = listing.get('hwb_value')
        
        if energy_class:
            if energy_class in ['G', 'F']:
                score += 1.5
            elif energy_class in ['E', 'D']:
                score += 1
            elif energy_class in ['C', 'C+']:
                score += 0.5
            # A and B classes get 0 points
        elif hwb_value:
            if hwb_value > 150:
                score += 1.5
            elif hwb_value > 100:
                score += 1
            elif hwb_value > 50:
                score += 0.5
            # Lower values get 0 points
        
        # Condition factor (0-1 point)
        condition = listing.get('condition', '').lower()
        if 'sanierungsbedürftig' in condition or 'renovierungsbedürftig' in condition:
            score += 1
        elif 'altbau' in condition and 'renoviert' not in condition:
            score += 0.7
        elif 'schlecht' in condition or 'mangelhaft' in condition:
            score += 0.8
        elif 'erstbezug' in condition or 'neu' in condition:
            score += 0  # No renovation needed
        
        # Heating type factor (0-0.5 points)
        heating_type = listing.get('heating_type', '').lower()
        if 'kohle' in heating_type or 'öl' in heating_type:
            score += 0.5
        elif 'gas' in heating_type and 'kondens' not in heating_type:
            score += 0.3
        # Modern heating systems get 0 points
        
        # Convert to 1-5 scale (inverted - higher score = more renovation needed)
        if score >= 4:
            return 5  # Major renovation needed
        elif score >= 3:
            return 4  # Significant renovation needed
        elif score >= 2:
            return 3  # Moderate renovation needed
        elif score >= 1:
            return 2  # Minor renovation needed
        else:
            return 1  # No renovation needed
            
    except Exception as e:
        logging.warning(f"Error calculating renovation needed rating: {e}")
        return 3  # Default to medium

def calculate_balcony_terrace(listing: Dict[str, Any]) -> bool:
    """
    Determine if property has balcony or terrace based on description.
    
    Returns:
        bool: True if balcony/terrace detected, False otherwise
    """
    try:
        # Check special features
        special_features = listing.get('special_features', [])
        if isinstance(special_features, list):
            for feature in special_features:
                if any(keyword in feature.lower() for keyword in ['balkon', 'terrasse', 'loggia']):
                    return True
        
        # Check title and description
        title = listing.get('title', '').lower()
        if any(keyword in title for keyword in ['balkon', 'terrasse', 'loggia']):
            return True
        
        # Check structured analysis if available
        structured_analysis = listing.get('structured_analysis', {})
        if isinstance(structured_analysis, dict):
            features = structured_analysis.get('features', [])
            if isinstance(features, list):
                for feature in features:
                    if any(keyword in feature.lower() for keyword in ['balkon', 'terrasse', 'loggia']):
                        return True
        
        return False
        
    except Exception as e:
        logging.warning(f"Error calculating balcony/terrace: {e}")
        return False

def calculate_floor_level(listing: Dict[str, Any]) -> int:
    """
    Extract floor level from property data.
    
    Returns:
        int: Floor level (0 for ground floor, 1+ for upper floors)
    """
    try:
        # Check if floor is already available
        floor = listing.get('floor')
        if floor is not None:
            return int(floor)
        
        # Try to extract from title or description
        title = listing.get('title', '').lower()
        if 'erdgeschoss' in title or 'parterre' in title:
            return 0
        elif '1. stock' in title or '1. og' in title:
            return 1
        elif '2. stock' in title or '2. og' in title:
            return 2
        elif '3. stock' in title or '3. og' in title:
            return 3
        elif '4. stock' in title or '4. og' in title:
            return 4
        elif '5. stock' in title or '5. og' in title:
            return 5
        
        # Default to ground floor if unknown
        return 0
        
    except Exception as e:
        logging.warning(f"Error calculating floor level: {e}")
        return 0

def calculate_all_ratings(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all ratings for a listing and return them as a dictionary.
    
    Returns:
        Dict containing calculated ratings
    """
    return {
        'potential_growth_rating': calculate_potential_growth_rating(listing),
        'renovation_needed_rating': calculate_renovation_needed_rating(listing),
        'balcony_terrace': calculate_balcony_terrace(listing),
        'floor_level': calculate_floor_level(listing)
    } 