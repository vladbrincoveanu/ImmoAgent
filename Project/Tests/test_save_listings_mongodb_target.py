import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Application import main as main_module
from Integration import mongodb_handler as mongodb_handler_module
from Domain.listing import Listing
from Domain.sources import Source


def test_save_listings_uses_configured_mongodb_uri_by_default():
    target_uri = "mongodb://atlas.example/immo"
    client = MagicMock()
    collection = client.__getitem__.return_value.__getitem__.return_value
    collection.find_one.return_value = None
    handler = MagicMock()

    listing = Listing(
        url="https://example.test/listing-1",
        source=Source.WILLHABEN,
        title="Test flat",
        price_total=210000,
        area_m2=70.0,
    )

    with patch.object(main_module, "load_config", return_value={"mongodb_uri": target_uri}), \
            patch.object(main_module.pymongo, "MongoClient", return_value=client) as mongo_client, \
            patch.object(mongodb_handler_module, "MongoDBHandler", return_value=handler) as handler_cls, \
            patch.object(main_module, "geocode_listing", return_value={"coordinate_source": "none"}):
        assert main_module.save_listings_to_mongodb([listing]) == 1

    handler_cls.assert_called_once_with(uri=target_uri)
    mongo_client.assert_called_once_with(target_uri)
