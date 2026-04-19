import pytest
import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from unittest.mock import patch, MagicMock
from Application.helpers.geocoding import geocode_listing, ViennaGeocoder
from Domain.location import Coordinates

class TestGeocodeListing:
    @patch.object(ViennaGeocoder, 'geocode_address')
    def test_exact_address_geocodes_and_sets_source_exact(self, mock_geocode):
        mock_geocode.return_value = Coordinates(48.2082, 16.3738)
        listing = {
            'url': 'https://example.com',
            'title': 'Test',
            'address': 'Schottengasse 1, 1010 Wien',
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'exact'
        assert result['coordinates'] == {'lat': 48.2082, 'lon': 16.3738}

    @patch.object(ViennaGeocoder, 'geocode_address')
    def test_landmark_hint_when_no_address(self, mock_geocode):
        mock_geocode.return_value = Coordinates(48.1967, 16.3400)
        listing = {
            'url': 'https://example.com',
            'title': 'Wohnung nahe Kettenbrückengasse U-Bahn',
            'address': None,
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'landmark'
        assert result['coordinates'] == {'lat': 48.1967, 'lon': 16.3400}

    def test_no_location_data_sets_source_none(self):
        listing = {
            'url': 'https://example.com',
            'title': 'Wohnung in Wien',
            'address': None,
            'coordinate_source': None,
            'coordinates': None,
        }
        result = geocode_listing(listing)
        assert result['coordinate_source'] == 'none'