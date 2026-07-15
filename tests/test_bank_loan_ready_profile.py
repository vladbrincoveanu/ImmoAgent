import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.buyer_profiles import get_profile

def test_bank_loan_ready_weights_sum_to_1():
    profile = get_profile('bank_loan_ready')
    total = sum(profile['weights'].values())
    assert abs(total - 1.0) < 0.001, f"weights sum to {total}, expected 1.0"

def test_bank_loan_ready_has_bezirk_score():
    profile = get_profile('bank_loan_ready')
    assert 'bezirk_score' in profile['weights']
    assert profile['weights']['bezirk_score'] == 0.10

def test_bank_loan_ready_has_is_provisionsfrei():
    profile = get_profile('bank_loan_ready')
    assert 'is_provisionsfrei' in profile['weights']
    assert profile['weights']['is_provisionsfrei'] == 0.05

def test_bank_loan_ready_hwb_weight_is_013():
    profile = get_profile('bank_loan_ready')
    assert profile['weights']['hwb_value'] == 0.13

def test_bank_loan_ready_school_weight_is_0():
    profile = get_profile('bank_loan_ready')
    assert profile['weights'].get('school_walk_minutes', 0) == 0.0
