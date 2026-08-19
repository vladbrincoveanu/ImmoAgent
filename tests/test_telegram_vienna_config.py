from Application.helpers import utils


def test_explicit_vienna_env_vars_supplement_main_only_config(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_VIENNA_TOKEN", "vienna-token-from-env")
    monkeypatch.setenv("TELEGRAM_BOT_VIENNA_CHAT_ID", "vienna-chat-from-env")

    config = {
        "telegram": {
            "telegram_main": {
                "bot_token": "main-token",
                "chat_id": "main-chat",
            }
        }
    }

    result = utils.supplement_config_with_env_vars(config)

    assert result["telegram"]["telegram_vienna"] == {
        "bot_token": "vienna-token-from-env",
        "chat_id": "vienna-chat-from-env",
    }


def test_no_config_does_not_fallback_vienna_to_main_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_MAIN_BOT_TOKEN", "main-token-from-env")
    monkeypatch.setenv("TELEGRAM_MAIN_CHAT_ID", "main-chat-from-env")
    monkeypatch.delenv("TELEGRAM_BOT_VIENNA_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_VIENNA_CHAT_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    previous_config = utils._config
    previous_project_root = utils._project_root
    utils._config = None
    utils._project_root = str(tmp_path)

    try:
        config = utils.load_config()
    finally:
        utils._config = previous_config
        utils._project_root = previous_project_root

    assert config["telegram"]["telegram_main"] == {
        "bot_token": "main-token-from-env",
        "chat_id": "main-chat-from-env",
    }
    assert config["telegram"]["telegram_vienna"] == {
        "bot_token": None,
        "chat_id": None,
    }
