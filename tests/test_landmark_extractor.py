import pytest
import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.helpers.landmark_extractor import extract_landmark_hint

class TestExtractLandmarkHint:
    def test_ubahn_nahe_pattern(self):
        result = extract_landmark_hint("3-Zi nahe Kettenbrückengasse U-Bahn")
        assert result == "Kettenbrückengasse U-Bahn, Wien, Austria"

    def test_ubahn_naheen_pattern(self):
        result = extract_landmark_hint("Wohnung nahen Pilgramgasse U-Bahn")
        assert result == "Pilgramgasse U-Bahn, Wien, Austria"

    def test_ubahn_standalone(self):
        result = extract_landmark_hint("Kettenbrückengasse U-Bahn in der Nähe")
        assert result == "Kettenbrückengasse U-Bahn, Wien, Austria"

    def test_strassenbahn_pattern(self):
        result = extract_landmark_hint("Wohnung in der Nähe von Pilgramgasse Straßenbahn")
        assert result == "Pilgramgasse, Wien, Austria"

    def test_no_hint_returns_none(self):
        result = extract_landmark_hint("Schöne 3-Zimmer-Wohnung in Margareten")
        assert result is None

    def test_empty_string(self):
        result = extract_landmark_hint("")
        assert result is None

    def test_none_input(self):
        result = extract_landmark_hint(None)
        assert result is None