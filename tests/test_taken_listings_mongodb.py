import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_price_history_on_re_scrape():
    """When same URL re-scrapped with different price, old price pushed to history"""
    from Integration.mongodb_handler import MongoDBHandler
    from unittest.mock import MagicMock, patch

    with patch.object(MongoDBHandler, '__init__', lambda self: None):
        mongo = MongoDBHandler()
        mongo.collection = MagicMock()
        mongo.client = MagicMock()

        mongo.collection.find_one.return_value = None
        mongo.collection.insert_one.return_value = MagicMock()

        listing1 = {
            'url': 'https://example.com/listing1',
            'title': 'Test Listing',
            'price_total': 400000,
            'area_m2': 80,
            'rooms': 3,
            'source_enum': 'willhaben',
            'processed_at': 1700000000,
        }
        result = mongo.upsert_listing_with_history(listing1)
        assert result == True
        insert_call = mongo.collection.insert_one.call_args[0][0]
        assert insert_call['first_scraped_at'] is not None
        assert insert_call['price_at_scrape'] == 400000
        assert insert_call['price_history'] == []

print("✅ Price history test written")

def test_mark_listing_taken():
    """mark_listing_taken sets listing_status=taken and url_is_valid=False"""
    from Integration.mongodb_handler import MongoDBHandler
    from unittest.mock import MagicMock, patch
    from datetime import datetime

    with patch.object(MongoDBHandler, '__init__', lambda self: None):
        mongo = MongoDBHandler()
        mongo.collection = MagicMock()
        mongo.collection.update_one.return_value = MagicMock(modified_count=1)

        result = mongo.mark_listing_taken('https://example.com/listing1')
        assert result == True
        call_args = mongo.collection.update_one.call_args
        set_fields = call_args[0][1]['$set']
        assert set_fields['listing_status'] == 'taken'
        assert set_fields['url_is_valid'] == False
        assert 'taken_at' in set_fields

print("✅ mark_listing_taken test written")

if __name__ == '__main__':
    test_price_history_on_re_scrape()
    test_mark_listing_taken()
    print("All tests passed")
