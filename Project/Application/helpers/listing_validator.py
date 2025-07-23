#!/usr/bin/env python3
"""
Listing validation utilities
Common logic for validating property listings across the application
"""

import logging
from typing import Dict, Any

def is_valid_listing(listing: Dict[str, Any]) -> bool:
    """
    Validate if a listing has realistic prices and data
    
    Args:
        listing: Listing dictionary
        
    Returns:
        bool: True if listing is valid, False if garbage
    """
    try:
        price_total = listing.get('price_total', 0)
        area_m2 = listing.get('area_m2', 0)
        
        # Skip if missing essential data
        if not price_total or not area_m2:
            return False
        
        # Calculate price per m²
        price_per_m2 = price_total / area_m2
        
        # Vienna price validation rules
        # Minimum realistic price per m² in Vienna (even for very cheap areas)
        min_price_per_m2 = 1000  # €1,000/m² minimum
        
        # Maximum realistic price per m² in Vienna (even for luxury areas)
        max_price_per_m2 = 25000  # €25,000/m² maximum
        
        # Check if price per m² is realistic
        if price_per_m2 < min_price_per_m2:
            logging.info(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (too cheap)")
            return False
        
        if price_per_m2 > max_price_per_m2:
            logging.info(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (too expensive)")
            return False
        
        # Additional checks for obviously wrong data
        if price_total < 50000:  # Less than €50k total price is suspicious
            logging.info(f"🚫 Filtered out garbage: €{price_total:,} total price (too low)")
            return False
        
        if area_m2 < 20:  # Less than 20m² is suspicious
            logging.info(f"🚫 Filtered out garbage: {area_m2}m² area (too small)")
            return False
        
        # Check monthly payment filter (below €2,000)
        monthly_payment = listing.get('monthly_payment', {})
        if monthly_payment and isinstance(monthly_payment, dict):
            total_monthly = monthly_payment.get('total_monthly', 0)
            if total_monthly > 2000:  # More than €2,000 monthly payment
                logging.info(f"🚫 Filtered out expensive: €{total_monthly:,.0f} monthly payment (above €2,000)")
                return False
        
        return True
        
    except Exception as e:
        logging.error(f"🚫 Error validating listing: {e}")
        return False

def filter_valid_listings(listings: list, limit: int = None) -> list:
    """
    Filter a list of listings to only include valid ones
    
    Args:
        listings: List of listing dictionaries
        limit: Maximum number of listings to return (None for all)
        
    Returns:
        list: Filtered list of valid listings
    """
    valid_listings = []
    for listing in listings:
        if is_valid_listing(listing):
            valid_listings.append(listing)
            if limit and len(valid_listings) >= limit:
                break
    
    return valid_listings

def get_validation_stats(listings: list) -> Dict[str, int]:
    """
    Get statistics about listing validation
    
    Args:
        listings: List of listing dictionaries
        
    Returns:
        dict: Statistics about validation results
    """
    total = len(listings)
    valid = 0
    invalid = 0
    
    for listing in listings:
        if is_valid_listing(listing):
            valid += 1
        else:
            invalid += 1
    
    return {
        'total': total,
        'valid': valid,
        'invalid': invalid,
        'valid_percentage': (valid / total * 100) if total > 0 else 0
    } 