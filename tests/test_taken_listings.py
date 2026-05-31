import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_mark_taken_listings_head_404():
    """HEAD 404 marks listing as taken"""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [
        {'_id': 1, 'url': 'https://example.com/404', 'source_enum': 'willhaben'}
    ]
    mock_mongo.mark_listing_taken = MagicMock(return_value=True)

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=404)
        result = mark_taken_listings(mock_mongo, source_filter=['willhaben'])

    assert result['newly_taken'] == 1
    mock_mongo.mark_listing_taken.assert_called_once_with('https://example.com/404')

def test_mark_taken_listings_head_200_derstandard_soft404():
    """DerStandard 200 with soft 404 body marks listing as taken"""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [
        {'_id': 2, 'url': 'https://derstandard.at/listing', 'source_enum': 'derstandard'}
    ]
    mock_mongo.mark_listing_taken = MagicMock(return_value=True)

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=200)
        with patch('Application.cleanup.requests.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                iter_content=lambda size: [b'diese anzeige wurde entfernt']
            )
            result = mark_taken_listings(mock_mongo, source_filter=['derstandard'])

    assert result['newly_taken'] == 1

def test_daily_revalidation_batch_processing():
    """Daily revalidation processes in batches with delay"""
    from Application.cleanup import daily_revalidation
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [
        {'_id': i, 'url': f'https://example.com/{i}', 'source_enum': 'willhaben'}
        for i in range(60)
    ]
    mock_mongo.mark_listing_taken = MagicMock(return_value=False)

    with patch('Application.cleanup.mark_taken_listings') as mock_mark:
        mock_mark.return_value = {"checked": 20, "newly_taken": 2, "already_taken": 0}
        result = daily_revalidation(mock_mongo, batch_size=20)

    assert result['checked'] == 60
    assert mock_mark.call_count == 3  # 3 batches of 20

print("✅ Tests written")

if __name__ == '__main__':
    test_mark_taken_listings_head_404()
    test_mark_taken_listings_head_200_derstandard_soft404()
    test_daily_revalidation_batch_processing()
    print("All tests passed")