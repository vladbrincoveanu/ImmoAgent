#!/usr/bin/env python3
"""
Listing validation utilities
Common logic for validating property listings across the application
"""

import logging
import hashlib
import re
import unicodedata
from typing import Dict, Any
from Application.buyer_profiles import GLOBAL_VALIDATION


def _norm(s: str) -> str:
    """Lowercase, fold umlauts/ß, collapse whitespace, strip non-alnum runs to single space."""
    s = s.lower().strip()
    s = s.replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compute_xsrc_fingerprint(listing) -> "str | None":
    """Source-INDEPENDENT fingerprint for co-op units so the same unit on
    Willhaben and on its Bauträger site collapse to one record.
    Key = md5(norm(bautraeger)|norm(address)|round(area)|rooms). No source, no price.
    Returns None when bautraeger or address is missing (weak key → don't collapse)."""
    if not getattr(listing, "bautraeger", None) or not getattr(listing, "address", None):
        return None
    area = listing.area_m2
    area_key = str(int(round(area))) if area else ""
    rooms_key = str(listing.rooms) if listing.rooms is not None else ""
    raw = f"{_norm(listing.bautraeger)}|{_norm(listing.address)}|{area_key}|{rooms_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def compute_content_fingerprint(listing: Dict[str, Any]) -> str:
    """
    Compute a content fingerprint hash for dedup based on key property fields.
    Used to detect duplicate listings that have different URLs (same agent, same property).
    """
    key_fields = (
        f"{listing.get('title', '')}"
        f"{listing.get('area_m2', '')}"
        f"{listing.get('rooms', '')}"
        f"{listing.get('bezirk', '')}"
        f"{listing.get('source_enum', listing.get('source', ''))}"
    )
    return hashlib.md5(key_fields.encode('utf-8')).hexdigest()

def is_valid_listing(listing: Dict[str, Any], skip_rental_filter: bool = False) -> bool:
    """
    Validate if a listing has realistic prices and data

    Args:
        listing: Listing dictionary
        skip_rental_filter: If True, skip the "unbefristet vermietete" rental filter (for owner-occupier profiles)

    Returns:
        bool: True if listing is valid, False if garbage
    """
    try:
        price_total = listing.get('price_total')
        area_m2 = listing.get('area_m2')

        # Allow missing price/area to pass (lenient - some listings have price on request)
        if price_total is None or area_m2 is None or area_m2 <= 0:
            return True

        # Calculate price per m²
        price_per_m2 = price_total / area_m2

        # Vienna price validation rules using GLOBAL_VALIDATION thresholds
        if price_per_m2 < GLOBAL_VALIDATION['min_price_per_m2']:
            logging.info(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (below min {GLOBAL_VALIDATION['min_price_per_m2']})")
            return False

        if price_per_m2 > GLOBAL_VALIDATION['max_price_per_m2']:
            logging.info(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (above max {GLOBAL_VALIDATION['max_price_per_m2']})")
            return False

        # Check monthly payment filter (below €2,500)
        monthly_payment = listing.get('monthly_payment', {})
        if monthly_payment and isinstance(monthly_payment, dict):
            total_monthly = monthly_payment.get('total_monthly', 0)
            if total_monthly > 2500:  # More than €2,500 monthly payment
                logging.info(f"🚫 Filtered out expensive: €{total_monthly:,.0f} monthly payment (above €2,500)")
                return False

        # Extract text fields needed for both rental and price-on-request filters
        title = (listing.get('title') or '').lower()
        description = (listing.get('description') or '').lower()
        special_features = listing.get('special_features', []) or []

        # Filter out "unbefristet vermietete" (indefinitely rented) properties
        if not skip_rental_filter:
            rental_keywords = [
                'unbefristet vermietet', 'unbefristet vermietete', 'unbefristet zum', 'unbefristet an',
                'vermietet', 'vermietete', 'vermietung', 'vermietungs', 'vermietbar',
                'bereits vermietet', 'aktuell vermietet', 'ist vermietet', 'wird vermietet',
                'miete', 'mieter', 'mietzins', 'mietvertrag', 'mietobjekt', 'mietwohnung',
                'mieteinnahmen', 'mietertrag', 'mietrendite',
                'rented', 'rental', 'tenant', 'tenancy', 'lease', 'leasing',
                'kat.a mietzins', 'kategorie a mietzins', 'kategorie-a mietzins',
                'mietzins kat.a', 'mietzins kategorie a', 'mietzins kategorie-a',
                'zum mietzins', 'an mietzins', 'mit mietzins', 'bei mietzins',
                'unbefristet', 'befristet', 'mietdauer', 'mietzeitraum'
            ]

            # Check title and description
            for keyword in rental_keywords:
                if keyword in title or keyword in description:
                    logging.info(f"🚫 Filtered out rental property: '{keyword}' found in title/description")
                    return False

            # Check special features
            if special_features:
                for feature in special_features:
                    feature_lower = str(feature).lower()
                    for keyword in rental_keywords:
                        if keyword in feature_lower:
                            logging.info(f"🚫 Filtered out rental property: '{keyword}' found in special features")
                            return False

        # Filter out "Preis auf Anfrage" (price on request) properties
        price_on_request_keywords = [
            'preis auf anfrage', 'price on request', 'auf anfrage', 'on request',
            'preis nach vereinbarung', 'price by arrangement', 'nach vereinbarung',
            'preis n.v.', 'price n.v.', 'n.v.', 'n/a', 'na', 'tba', 'to be announced',
            'preis wird bekanntgegeben', 'price to be announced', 'wird bekanntgegeben'
        ]

        # Check title and description for price on request indicators
        for keyword in price_on_request_keywords:
            if keyword in title or keyword in description:
                logging.info(f"🚫 Filtered out price on request property: '{keyword}' found in title/description")
                return False

        # Check special features for price on request indicators
        if special_features:
            for feature in special_features:
                feature_lower = str(feature).lower()
                for keyword in price_on_request_keywords:
                    if keyword in feature_lower:
                        logging.info(f"🚫 Filtered out price on request property: '{keyword}' found in special features")
                        return False

        # Stricter scoring requirements for properties above 400k
        if price_total > 400000:
            score = listing.get('score')
            if score is None:
                score = 0
            if score < 40:  # Properties above 400k need a score of at least 40
                logging.info(f"🚫 Filtered out expensive property with low score: €{price_total:,} with score {score} (needs 40+)")
                return False

        return True
        
    except Exception as e:
        logging.error(f"🚫 Error validating listing: {e}")
        return False

def filter_valid_listings(listings: list, limit: int = None, skip_rental_filter: bool = False) -> list:
    """
    Filter a list of listings to only include valid ones

    Args:
        listings: List of listing dictionaries
        limit: Maximum number of listings to return (None for all)
        skip_rental_filter: If True, skip the rental filter (for owner-occupier profiles)

    Returns:
        list: Filtered list of valid listings
    """
    valid_listings = []
    for listing in listings:
        if is_valid_listing(listing, skip_rental_filter=skip_rental_filter):
            valid_listings.append(listing)
            if limit and len(valid_listings) >= limit:
                break

    return valid_listings

def get_validation_stats(listings: list) -> Dict[str, Any]:
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