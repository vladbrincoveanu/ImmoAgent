# Configuration Management

This document explains the configuration structure for the Immo-Scouter project.

## Configuration Files

### 1. Main Configuration: `config.json` (Root Directory)

**Location**: `/config.json` (in the project root directory)

**Purpose**: Production configuration used by the main application

**Features**:
- MongoDB connection settings
- Telegram bot tokens and chat IDs
- Scraping parameters
- Property filtering criteria
- Top5 report settings

**Example**:
```json
{
  "mongodb_uri": "mongodb://admin:admin@localhost:27017/immo?authSource=admin",
  "openai_api_key": "your-api-key",
  "telegram": {
    "telegram_main": {
      "bot_token": "your-bot-token",
      "chat_id": "your-chat-id"
    }
  },
  "top5": {
    "limit": 5,
    "min_score": 40.0,
    "days_old": 7
  },
  "criteria": {
    "price_max": 1000000,
    "rooms_min": 3,
    "year_built_min": 1970
  }
}
```

### 2. Default Configuration Template: `config.json.default`

**Location**: `/config.json.default` (in the project root directory)

**Purpose**: Template file for new installations

**Usage**:
```bash
# Copy template to create your config
cp config.json.default config.json

# Edit with your settings
nano config.json
```

### 3. Test Configuration: `Tests/test_config.json`

**Location**: `/Tests/test_config.json`

**Purpose**: Configuration for testing with safe, non-production values

**Features**:
- Test database (`test_immo`)
- Fake Telegram tokens
- Reduced scraping limits
- Lower score thresholds

**Usage in Tests**:
```python
from Tests.test_utils import load_test_config, setup_test_environment

# Set up test environment
setup_test_environment()

# Load test config
config = load_test_config()
```

## Configuration Loading Logic

The application uses a smart configuration loading system:

### 1. Project Root Detection

The `get_project_root()` function finds the project root by:
1. Looking for `README.md` files
2. Checking for `config.json` in the same directory
3. If no `config.json` found, checking parent directory
4. Using the directory with `config.json` as the project root

### 2. Configuration Loading Priority

The `load_config()` function loads configuration in this order:

1. **Primary**: `{project_root}/config.json`
2. **Fallback**: Legacy paths (`config.json`, `immo-scouter/config.json`)

### 3. Test Configuration

When running tests:
1. Set `IMMO_SCOUTER_TEST_MODE=true` environment variable
2. Use `Tests/test_config.json` instead of main config
3. Connect to test database (`test_immo`)

## Configuration Sections

### MongoDB Settings
```json
{
  "mongodb_uri": "mongodb://admin:admin@localhost:27017/immo?authSource=admin"
}
```

### Telegram Configuration
```json
{
  "telegram": {
    "telegram_main": {
      "bot_token": "your-main-bot-token",
      "chat_id": "your-main-chat-id"
    },
    "telegram_vienna": {
      "bot_token": "your-vienna-bot-token",
      "chat_id": "your-vienna-chat-id"
    },
    "min_score_threshold": 40
  }
}
```

#### Telegram Chat Types

**Channels** (for property notifications):
- Chat ID format: `-100xxxxxxxxxx` (starts with `-100`)
- Example: `-1002541247936` (ViennaApartmentsLive channel)
- Used for: Property listings, top5 reports, public announcements
- Anyone can join and view messages

**Private Chats** (for logs and errors):
- Chat ID format: `xxxxxxxxxx` (positive number)
- Example: `1790488473` (your private chat with the bot)
- Used for: Error logs, debug information, private notifications
- Only you can see these messages

#### Configuration Best Practices

1. **Main Channel**: Use a public channel for property notifications
   ```json
   "telegram_main": {
     "bot_token": "your-bot-token",
     "chat_id": "-1002541247936"  // Channel ID
   }
   ```

2. **Dev Chat**: Use a private chat for logs and errors
   ```json
   "telegram_dev": {
     "bot_token": "your-bot-token", 
     "chat_id": "1790488473"  // Private chat ID
   }
   ```

3. **Bot Permissions**: Ensure your bot has permission to post to the channel
   - Add bot as channel administrator
   - Grant "Post Messages" permission

### Top5 Report Settings
```json
{
  "top5": {
    "limit": 5,
    "min_score": 40.0,
    "days_old": 7
  }
}
```

### Property Filtering Criteria
```json
{
  "criteria": {
    "price_max": 1000000,
    "price_per_m2_max": 20000,
    "area_m2_min": 20,
    "rooms_min": 3,
    "year_built_min": 1970,
    "districts": ["1010", "1020", "1030", ...]
  }
}
```

### Scraping Configuration
```json
{
  "scraping": {
    "timeout": 30,
    "delay_between_requests": 1,
    "selenium_wait_time": 10
  },
  "max_pages": 5
}
```

## Environment Variables

The application also supports environment variables for sensitive data:

```bash
# MongoDB
export MONGODB_URI="mongodb://user:pass@host:port/db"

# OpenAI
export OPENAI_API_KEY="your-api-key"

# Telegram
export TELEGRAM_MAIN_BOT_TOKEN="your-bot-token"
export TELEGRAM_MAIN_CHAT_ID="your-chat-id"

# Test Mode
export IMMO_SCOUTER_TEST_MODE="true"
```

## Usage Examples

### Running Main Application
```bash
# From project root
PYTHONPATH=Project python Project/Application/main.py

# From Project directory
cd Project
PYTHONPATH=. python Application/main.py
```

### Running Top5 Report
```bash
# From project root
PYTHONPATH=Project python Project/run_top5.py

# From Project directory
cd Project
PYTHONPATH=. python run_top5.py
```

### Running Tests
```bash
# Test with test configuration
python Tests/test_top5_mongodb_only.py

# Test with production configuration
IMMO_SCOUTER_TEST_MODE=false python Tests/test_top5_mongodb_only.py
```

## Security Best Practices

1. **Never commit real credentials** to version control
2. **Use environment variables** for sensitive data
3. **Use test configuration** for automated tests
4. **Keep production config** separate from development
5. **Regularly rotate** API keys and tokens

## Troubleshooting

### Common Issues

1. **"No config file found"**
   - Ensure `config.json` exists in project root
   - Check file permissions
   - Verify JSON syntax

2. **"MongoDB authentication required"**
   - Check MongoDB connection string
   - Verify credentials
   - Ensure database exists

3. **"Telegram connection failed"**
   - Verify bot token and chat ID
   - Check bot permissions
   - Ensure chat exists

### Debug Configuration Loading

```python
from Application.helpers.utils import get_project_root, load_config

# Check project root
print(f"Project root: {get_project_root()}")

# Load and inspect config
config = load_config()
print(f"Config keys: {list(config.keys())}")
```

## Migration Guide

### From Old Structure

If you have an old configuration structure:

1. **Move config to root**: Move your `config.json` to the project root directory
2. **Update paths**: Update any hardcoded paths in your scripts
3. **Test loading**: Verify configuration loads correctly
4. **Remove duplicates**: Delete any duplicate config files

### To New Structure

1. **Create main config**: Copy `config.json.default` to `config.json`
2. **Add your settings**: Update with your actual values
3. **Create test config**: Run `python Tests/test_utils.py` to create test config
4. **Test everything**: Run tests to verify configuration works 