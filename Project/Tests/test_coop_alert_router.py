"""Co-op alert routing: which Telegram channel a co-op hit goes to.

The bug this guards: TELEGRAM_COOP_CHANNEL_ID was never set, the workflow warned
non-fatally, and the poll ran green for weeks while sending nothing. A missing
channel must be visible, not inferred from silence.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.coop_alert_router import missing_channels, route  # noqa: E402


def test_mygewo_unit_routes_to_coop_channel(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    assert route("mygewo") == "-100111"


def test_private_transfer_routes_to_its_own_channel(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.setenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", "-100222")
    assert route("private_transfer") == "-100222"


def test_private_transfer_does_not_fall_back_to_coop_channel(monkeypatch):
    """Urgent Ablöse hits must not be buried in the bulk mygewo feed."""
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.delenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", raising=False)
    assert route("private_transfer") is None


def test_unknown_kind_routes_nowhere(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    assert route("something_else") is None


def test_empty_secret_is_treated_as_unset(monkeypatch):
    """An empty repo secret reads back as "" — that is not a valid chat id."""
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "")
    assert route("mygewo") is None
    assert "TELEGRAM_COOP_CHANNEL_ID" in missing_channels()


def test_missing_channels_lists_every_unset_secret(monkeypatch):
    monkeypatch.delenv("TELEGRAM_COOP_CHANNEL_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", raising=False)
    assert set(missing_channels()) == {
        "TELEGRAM_COOP_CHANNEL_ID", "TELEGRAM_PRIVATE_COOP_CHANNEL_ID"}


def test_missing_channels_empty_when_all_set(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.setenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", "-100222")
    assert missing_channels() == []
