#!/usr/bin/env python3
"""
Test script to verify Telegram bot connections, config, and handler security.
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Application.main import load_config
from Integration.telegram_bot import TelegramBot, TelegramLogHandler

def test_telegram_config():
    print("\n🔎 Checking Telegram config...")
    config = load_config()
    assert config, "Config could not be loaded!"
    telegram_config = config.get('telegram', {})
    main_config = telegram_config.get('telegram_main', {})
    dev_config = telegram_config.get('telegram_dev', {})
    
    main_token = main_config.get('bot_token')
    main_chat_id = main_config.get('chat_id')
    dev_token = dev_config.get('bot_token')
    dev_chat_id = dev_config.get('chat_id')
    
    assert main_token and main_chat_id, "Main Telegram bot config missing!"
    assert dev_token and dev_chat_id, "Dev Telegram bot config missing!"
    assert (main_token != dev_token or main_chat_id != dev_chat_id), "Main and dev Telegram credentials must be different!"
    print("✅ Telegram config present and main/dev are different.")
    return main_token, main_chat_id, dev_token, dev_chat_id

def test_telegram_connection(token, chat_id, label):
    print(f"\n🔎 Testing {label} Telegram bot connection...")
    bot = TelegramBot(token, chat_id)
    ok = bot.test_connection()
    assert ok, f"{label} Telegram bot connection failed!"
    print(f"✅ {label} Telegram bot connection successful.")
    return bot

def test_dev_handler_security(main_token, main_chat_id, dev_token, dev_chat_id):
    print("\n🔎 Testing dev log handler security...")
    # Should succeed for dev bot
    dev_bot = TelegramBot(dev_token, dev_chat_id)
    try:
        handler = TelegramLogHandler(dev_bot, is_dev_channel=True)
        print("✅ Dev log handler attached to dev bot (allowed)")
    except Exception as e:
        print(f"❌ Unexpected error for dev bot: {e}")
        assert False, "Dev handler should be allowed for dev bot"
    # Should fail for main bot
    main_bot = TelegramBot(main_token, main_chat_id)
    try:
        handler = TelegramLogHandler(main_bot, is_dev_channel=True)
        print("❌ Dev log handler attached to main bot (should not happen!)")
        assert False, "Dev handler should NOT be allowed for main bot!"
    except RuntimeError as e:
        print(f"✅ Security check: {e}")
    except Exception as e:
        print(f"❌ Unexpected error for main bot: {e}")
        assert False, "Unexpected error for main bot"

def test_dev_logging(dev_token, dev_chat_id):
    print("\n🔎 Testing dev log handler logging...")
    dev_bot = TelegramBot(dev_token, dev_chat_id)
    logger = logging.getLogger("dev_test_logger")
    handler = TelegramLogHandler(dev_bot, is_dev_channel=True)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("This is a test INFO log for dev channel.")
    logger.warning("This is a test WARNING log for dev channel.")
    logger.error("This is a test ERROR log for dev channel.")
    logger.removeHandler(handler)
    print("✅ Sent test logs to dev channel. Check your dev Telegram.")

def main():
    main_token, main_chat_id, dev_token, dev_chat_id = test_telegram_config()
    test_telegram_connection(main_token, main_chat_id, "Main")
    test_telegram_connection(dev_token, dev_chat_id, "Dev")
    test_dev_handler_security(main_token, main_chat_id, dev_token, dev_chat_id)
    test_dev_logging(dev_token, dev_chat_id)
    print("\n🎉 All Telegram connection/config tests passed!")

if __name__ == "__main__":
    main() 