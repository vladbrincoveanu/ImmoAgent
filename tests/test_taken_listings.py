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

def test_daily_revalidation_delegates_to_one_revalidation_pass():
    """Daily revalidation delegates one rate-limited pass over active listings."""
    from Application.cleanup import daily_revalidation
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()

    with patch('Application.cleanup.mark_taken_listings') as mock_mark:
        expected = {"checked": 60, "newly_taken": 2, "already_taken": 0}
        mock_mark.return_value = expected
        result = daily_revalidation(mock_mongo)

    assert result == expected
    mock_mark.assert_called_once_with(
        mock_mongo,
        source_filter=None,
        timeout=8,
        rate_limit_delay=0.5,
    )

def test_mark_taken_listings_probes_builder_url_but_marks_canonical_url():
    """Builder-offer removal marks the stored MyGEWO record as taken."""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    canonical_url = 'https://mygewo.at/genossenschaftswohnungen/angebot/unit'
    builder_url = 'https://builder.example/offers/unit'
    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()

    def find(_query, projection):
        assert projection.get('builder_url') == 1
        return [{
            '_id': 3,
            'url': canonical_url,
            'builder_url': builder_url,
            'source_enum': 'genossenschaft',
        }]

    mock_mongo.collection.find.side_effect = find
    mock_mongo.mark_listing_taken = MagicMock(return_value=True)

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=410)
        result = mark_taken_listings(
            mock_mongo,
            source_filter=['genossenschaft'],
        )

    assert result['newly_taken'] == 1
    assert mock_head.call_count == 1
    assert [call.args[0] for call in mock_head.call_args_list] == [builder_url]
    mock_mongo.mark_listing_taken.assert_called_once_with(canonical_url)

print("✅ Tests written")

if __name__ == '__main__':
    test_mark_taken_listings_head_404()
    test_mark_taken_listings_head_200_derstandard_soft404()
    test_daily_revalidation_delegates_to_one_revalidation_pass()
    test_mark_taken_listings_probes_builder_url_but_marks_canonical_url()
    print("All tests passed")
