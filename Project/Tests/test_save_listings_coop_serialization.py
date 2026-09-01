import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Application import main as main_module
from Integration import mongodb_handler as mongodb_handler_module
from Domain.listing import Listing
from Domain.sources import Source


def test_generic_save_serializes_coop_metadata_and_source_values():
    client = MagicMock()
    collection = client.__getitem__.return_value.__getitem__.return_value
    collection.find_one.return_value = None
    collection.insert_one.return_value.inserted_id = "coop-1"
    handler = MagicMock()

    listing = Listing(
        url="https://mygewo.at/angebot/coop-1",
        source=Source.GENOSSENSCHAFT,
        title="1100 Wien - 2 Zimmer",
        address="Musterstraße 1, 1100 Wien",
        bezirk="1100",
        price_total=720,
        area_m2=60,
        rooms=2,
        bautraeger="ÖVW",
        is_genossenschaft=True,
        coop_source="bautraeger_direct",
        buyable=False,
        builder_url="https://builder.example/coop-1",
    )

    with patch.object(main_module.pymongo, "MongoClient", return_value=client), \
            patch.object(mongodb_handler_module, "MongoDBHandler", return_value=handler), \
            patch.object(main_module, "geocode_listing", return_value={"coordinate_source": "none"}):
        assert main_module.save_listings_to_mongodb([listing], mongo_uri="mongodb://fake/") == 1

    stored = collection.insert_one.call_args.args[0]
    assert stored["source"] == "genossenschaft"
    assert stored["source_enum"] == "genossenschaft"
    assert stored["coop_source"] == "bautraeger_direct"
    assert stored["buyable"] is False
    assert stored["price_per_m2"] == 12
