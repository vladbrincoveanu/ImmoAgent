import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Project"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Application.helpers import utils
import setup_vienna_channel


class TestTelegramViennaConfig(unittest.TestCase):
    def setUp(self):
        self._previous_config = utils._config
        self._previous_project_root = utils._project_root
        self._previous_cwd = os.getcwd()
        utils._config = None
        utils._project_root = None

    def tearDown(self):
        os.chdir(self._previous_cwd)
        utils._config = self._previous_config
        utils._project_root = self._previous_project_root

    def test_explicit_vienna_env_vars_supplement_main_only_config(self):
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_VIENNA_TOKEN": "vienna-token-from-env",
                "TELEGRAM_BOT_VIENNA_CHAT_ID": "vienna-chat-from-env",
            },
            clear=False,
        ):
            config = {
                "telegram": {
                    "telegram_main": {
                        "bot_token": "main-token",
                        "chat_id": "main-chat",
                    }
                }
            }

            result = utils.supplement_config_with_env_vars(config)

        self.assertEqual(
            result["telegram"]["telegram_vienna"],
            {
                "bot_token": "vienna-token-from-env",
                "chat_id": "vienna-chat-from-env",
            },
        )

    def test_no_config_does_not_fallback_vienna_to_main_env(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "TELEGRAM_MAIN_BOT_TOKEN": "main-token-from-env",
                "TELEGRAM_MAIN_CHAT_ID": "main-chat-from-env",
            },
            clear=True,
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            os.chdir(temp_dir)
            utils._project_root = temp_dir
            config = utils.load_config()

        self.assertEqual(
            config["telegram"]["telegram_main"],
            {
                "bot_token": "main-token-from-env",
                "chat_id": "main-chat-from-env",
            },
        )
        self.assertEqual(
            config["telegram"]["telegram_vienna"],
            {
                "bot_token": None,
                "chat_id": None,
            },
        )
        self.assertNotIn("main-token-from-env", output.getvalue())
        self.assertNotIn("main-chat-from-env", output.getvalue())
        self.assertNotIn("mongodb://localhost:27017/immo", output.getvalue())

    def test_vienna_token_prefers_explicit_environment_value(self):
        config = {
            "telegram": {
                "telegram_vienna": {"bot_token": "file-vienna-token"}
            }
        }

        with patch.dict(
            os.environ,
            {"TELEGRAM_BOT_VIENNA_TOKEN": "env-vienna-token"},
            clear=True,
        ):
            self.assertEqual(
                setup_vienna_channel._get_vienna_bot_token(config),
                "env-vienna-token",
            )

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                setup_vienna_channel._get_vienna_bot_token(config),
                "file-vienna-token",
            )

    def test_resolve_config_path_prefers_root_then_project_legacy_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_config_path = os.path.join(temp_dir, "Project", "config.json")
            root_config_path = os.path.join(temp_dir, "config.json")
            os.makedirs(os.path.dirname(project_config_path))

            with patch.object(setup_vienna_channel, "get_project_root", return_value=temp_dir):
                self.assertEqual(
                    setup_vienna_channel._resolve_config_path(),
                    root_config_path,
                )

                with open(project_config_path, "w", encoding="utf-8") as config_file:
                    config_file.write("{}")
                self.assertEqual(
                    setup_vienna_channel._resolve_config_path(),
                    project_config_path,
                )

                with open(root_config_path, "w", encoding="utf-8") as config_file:
                    config_file.write("{}")
                self.assertEqual(
                    setup_vienna_channel._resolve_config_path(),
                    root_config_path,
                )

    def test_retry_session_constructs_with_retry_adapter(self):
        session = setup_vienna_channel._create_session_with_retry()
        try:
            adapter = session.get_adapter("https://")
            self.assertEqual(adapter.max_retries.total, 2)
            self.assertEqual(adapter.max_retries.status_forcelist, [500, 502, 503, 504])
        finally:
            session.close()

    def test_existing_config_preserves_vienna_token_and_main_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            original = {
                "telegram": {
                    "telegram_main": {
                        "bot_token": "main-file-token",
                        "chat_id": "main-file-chat",
                    },
                    "telegram_vienna": {
                        "bot_token": "file-vienna-token",
                        "chat_id": "old-vienna-chat",
                    },
                },
                "top5": {"limit": 5},
            }
            with open(config_path, "w", encoding="utf-8") as config_file:
                json.dump(original, config_file)

            setup_vienna_channel._write_vienna_channel_config(
                config_path, "new-vienna-chat"
            )

            with open(config_path, "r", encoding="utf-8") as config_file:
                updated = json.load(config_file)

        self.assertEqual(updated["telegram"]["telegram_main"], original["telegram"]["telegram_main"])
        self.assertEqual(updated["telegram"]["telegram_vienna"], {
            "bot_token": "file-vienna-token",
            "chat_id": "new-vienna-chat",
        })
        self.assertEqual(updated["top5"], {"limit": 5})

    def test_missing_config_writes_only_non_secret_vienna_channel_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")

            setup_vienna_channel._write_vienna_channel_config(
                config_path, "new-vienna-chat"
            )

            with open(config_path, "r", encoding="utf-8") as config_file:
                updated = json.load(config_file)

        self.assertEqual(
            updated,
            {"telegram": {"telegram_vienna": {"chat_id": "new-vienna-chat"}}},
        )
