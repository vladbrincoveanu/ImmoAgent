import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock
import Application.main
from Domain.listing import Listing
from Domain.sources import Source


class TestSaveListingsUrlReplace(unittest.TestCase):
    @patch('Application.main.pymongo.MongoClient')
    @patch('Application.main.MongoDBHandler')
    def test_replace_preserves_taken_status_and_pushes_price_history(self, mock_handler_cls, mock_client_cls):
        from Application.main import save_listings_to_mongodb

        mock_collection = MagicMock()
        mock_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_collection.find_one.return_value = {
            "_id": "xyz", "url": "https://www.willhaben.at/same-url",
            "listing_status": "taken", "taken_at": "2026-08-01T00:00:00",
            "price_total": 200000, "price_history": [],
        }

        listing = Listing(url="https://www.willhaben.at/same-url", source=Source.WILLHABEN,
                           title="Test flat", bezirk="1100", area_m2=70.0, rooms=3,
                           price_total=190000)

        save_listings_to_mongodb([listing], mongo_uri="mongodb://fake/")

        mock_collection.replace_one.assert_called_once()
        replaced_doc = mock_collection.replace_one.call_args[0][1]
        self.assertEqual(replaced_doc['listing_status'], 'taken')
        self.assertEqual(replaced_doc['taken_at'], "2026-08-01T00:00:00")
        self.assertEqual(len(replaced_doc['price_history']), 1)
        self.assertEqual(replaced_doc['price_history'][0]['price_total'], 200000)


if __name__ == '__main__':
    unittest.main()
