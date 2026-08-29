from unittest.mock import Mock

from Application import observability


def setup_function():
    observability._initialized = False


def teardown_function():
    observability._initialized = False


def test_sentry_is_disabled_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    sdk = Mock()

    assert observability.init_sentry(sdk) is False
    sdk.init.assert_not_called()


def test_sentry_initializes_with_the_configured_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    sdk = Mock()

    assert observability.init_sentry(sdk) is True
    sdk.init.assert_called_once_with(
        dsn="https://public@example.ingest.sentry.io/1",
        send_default_pii=True,
    )
    assert observability.init_sentry(sdk) is True
    sdk.init.assert_called_once()


def test_sentry_environment_is_forwarded_when_configured(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "test")
    sdk = Mock()

    assert observability.init_sentry(sdk) is True
    sdk.init.assert_called_once_with(
        dsn="https://public@example.ingest.sentry.io/1",
        send_default_pii=True,
        environment="test",
    )


def test_sentry_failure_does_not_stop_the_job(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    sdk = Mock()
    sdk.init.side_effect = RuntimeError("network unavailable")

    assert observability.init_sentry(sdk) is False
