import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scoring import normalize_value

def test_bezirk_score_1_normalizes_100():
    assert normalize_value('bezirk_score', 1) == 100.0

def test_bezirk_score_0_normalizes_0():
    assert normalize_value('bezirk_score', 0) == 0.0

def test_is_provisionsfrei_1_normalizes_100():
    assert normalize_value('is_provisionsfrei', 1) == 100.0

def test_is_provisionsfrei_0_normalizes_0():
    assert normalize_value('is_provisionsfrei', 0) == 0.0

def test_unknown_criterion_returns_0():
    assert normalize_value('nonexistent', 5) == 0.0
