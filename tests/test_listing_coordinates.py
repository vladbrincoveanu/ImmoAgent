#!/usr/bin/env python3
"""
Test script for listing coordinate fields
"""

import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import pytest
from Domain.listing import Listing
from Domain.sources import Source


def test_listing_has_coordinate_fields():
    """Listing dataclass should have coordinates, coordinate_source, landmark_hint fields."""
    url = "https://example.com"
    listing = Listing(url=url, source=Source.WILLHABEN)
    assert hasattr(listing, 'coordinates')
    assert hasattr(listing, 'coordinate_source')
    assert hasattr(listing, 'landmark_hint')


def test_listing_coordinate_fields_default_to_none():
    """New coordinate fields should default to None."""
    url = "https://example.com"
    listing = Listing(url=url, source=Source.WILLHABEN)
    assert listing.coordinates is None
    assert listing.coordinate_source is None
    assert listing.landmark_hint is None