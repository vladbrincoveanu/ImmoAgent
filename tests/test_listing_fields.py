import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Domain.listing import Listing
from Domain.sources import Source

def test_new_fields_exist_with_none_defaults():
    l = Listing(url='http://example.com', source=Source.WILLHABEN)
    assert hasattr(l, 'availability_status') and l.availability_status is None
    assert hasattr(l, 'rental_end_date') and l.rental_end_date is None
    assert hasattr(l, 'is_provisionsfrei') and l.is_provisionsfrei is None
    assert hasattr(l, 'bezirk_score') and l.bezirk_score is None
    assert hasattr(l, 'feasibility_passed') and l.feasibility_passed is None
    assert hasattr(l, 'feasibility_report') is not None
