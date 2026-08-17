import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Application.scraping import genossenschaft_scraper as gs


def test_module_imports_field_extractors():
    # genossenschaft_scraper must call the same coverage-fields extraction
    # helpers the other scrapers use, wherever description text is available.
    import inspect
    src = inspect.getsource(gs)
    assert "extract_doppelmakler" in src or "extract_maklerprovision_pct" in src
