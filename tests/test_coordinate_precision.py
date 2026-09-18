import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.main import compute_coordinate_precision_m


def test_exact_precision():
    assert compute_coordinate_precision_m("exact") == 10


def test_landmark_precision():
    assert compute_coordinate_precision_m("landmark") == 200


def test_none_precision():
    assert compute_coordinate_precision_m("none") is None
    assert compute_coordinate_precision_m(None) is None
