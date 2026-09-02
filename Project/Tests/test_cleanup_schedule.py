"""Cleanup scheduling contracts for the scheduled scrape job."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import Application.helpers.utils as utils  # noqa: E402
from Application.main import (  # noqa: E402
    cleanup_url_verification_enabled,
    should_run_cleanup,
)


def test_scheduled_cleanup_runs_only_in_the_morning():
    assert should_run_cleanup(True, False, datetime(2026, 9, 1, 6)) is True
    assert should_run_cleanup(True, False, datetime(2026, 9, 1, 11)) is False


def test_explicit_cleanup_can_run_outside_the_morning_window():
    assert should_run_cleanup(True, True, datetime(2026, 9, 1, 11)) is True
    assert should_run_cleanup(False, True, datetime(2026, 9, 1, 11)) is True


def test_url_sweep_is_opt_in_for_scheduled_cleanup():
    assert cleanup_url_verification_enabled({}, False) is False
    assert cleanup_url_verification_enabled({}, True) is True
    assert cleanup_url_verification_enabled({"verify_urls": True}, False) is True
    assert cleanup_url_verification_enabled({"verify_urls": False}, True) is True


def test_default_immo_kurier_feed_uses_dibeo_purchase_search(monkeypatch):
    monkeypatch.setattr(utils, "_config", None)
    monkeypatch.setattr(utils, "_project_root", None)

    config = utils.load_config()

    assert config["immo_kurier"]["search_url"].startswith(
        "https://www.dibeo.at/obj/wie/b"
    )
