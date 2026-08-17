import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock
import Application.main  # noqa: F401 - ensures Application.main is importable as an attribute for @patch
from Domain.listing import Listing
from Domain.sources import Source


class TestSaveListingsDedup(unittest.TestCase):
    @patch('Application.main.pymongo.MongoClient')
    @patch('Application.main.MongoDBHandler')
    def test_fingerprint_match_reactivates_taken_listing(self, mock_handler_cls, mock_client_cls):
        from Application.main import save_listings_to_mongodb

        mock_collection = MagicMock()
        mock_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = mock_collection
        # url match -> None (not a re-scrape of the same URL)
        # fingerprint match -> a previously-taken doc
        mock_collection.find_one.side_effect = [
            None,  # existing_by_url
            {"_id": "abc", "listing_status": "taken", "taken_at": None,
             "price_total": 200000, "price_history": [], "relist_events": [],
             "times_relisted": 0, "coordinates": {"lat": 48.2, "lon": 16.3}},
        ]

        listing = Listing(url="https://www.willhaben.at/new-url", source=Source.WILLHABEN,
                           title="Test flat", bezirk="1100", address="Musterstraße 1, 1100 Wien",
                           area_m2=70.0, rooms=3, price_total=210000)

        save_listings_to_mongodb([listing], mongo_uri="mongodb://fake/")

        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        set_payload = call_args[0][1]['$set']
        self.assertEqual(set_payload['listing_status'], 'active')
        self.assertEqual(set_payload['times_relisted'], 1)


if __name__ == '__main__':
    unittest.main()
