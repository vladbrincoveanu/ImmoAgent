# Immo-Scouter

A comprehensive real estate scraping and analysis system for Vienna, Austria.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- MongoDB
- Telegram Bot (optional)

### Installation
```bash
git clone <repository-url>
cd immo-scouter
pip install -r Project/requirements.txt
```

### Configuration
Copy `config.json.default` to `config.json` and update with your settings:

```json
{
  "mongodb_uri": "mongodb://localhost:27017/immo",
  "telegram": {
    "telegram_main": {
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    }
  }
}
```

## 🔧 Environment Variables for GitHub Actions

The application supports loading configuration from environment variables, perfect for GitHub Actions:

### Required Environment Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://user:pass@host:port/db` |
| `TELEGRAM_MAIN_BOT_TOKEN` | Telegram bot token for main channel | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `TELEGRAM_MAIN_CHAT_ID` | Telegram chat ID for main channel | `-1001234567890` |

### Optional Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_VIENNA_TOKEN` | Telegram bot token for Vienna channel | Uses main token |
| `TELEGRAM_BOT_VIENNA_CHAT_ID` | Telegram chat ID for Vienna channel | Uses main chat ID |
| `OLLAMA_BASE_URL` | Ollama API base URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `llama3.1:8b` |
| `OPENAI_API_KEY` | OpenAI API key | `null` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `MINIO_ENDPOINT` | MinIO server endpoint | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `MINIO_BUCKET_NAME` | MinIO bucket name | `immo-images` |

### GitHub Actions Workflow Example
```yaml
name: Run Immo-Scouter

on:
  schedule:
    - cron: '0 8 * * *'  # Run daily at 8 AM
  workflow_dispatch:  # Allow manual trigger

jobs:
  run-scraper:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        cd Project
        pip install -r requirements.txt
        
    - name: Run Immo-Scouter
      env:
        MONGODB_URI: ${{ secrets.MONGODB_URI }}
        TELEGRAM_MAIN_BOT_TOKEN: ${{ secrets.TELEGRAM_MAIN_BOT_TOKEN }}
        TELEGRAM_MAIN_CHAT_ID: ${{ secrets.TELEGRAM_MAIN_CHAT_ID }}
        TELEGRAM_BOT_VIENNA_TOKEN: ${{ secrets.TELEGRAM_BOT_VIENNA_TOKEN }}
        TELEGRAM_BOT_VIENNA_CHAT_ID: ${{ secrets.TELEGRAM_BOT_VIENNA_CHAT_ID }}
      run: |
        cd Project
        python run.py --send-to-telegram
        
    - name: Run Top5 Report
      env:
        MONGODB_URI: ${{ secrets.MONGODB_URI }}
        TELEGRAM_MAIN_BOT_TOKEN: ${{ secrets.TELEGRAM_MAIN_BOT_TOKEN }}
        TELEGRAM_MAIN_CHAT_ID: ${{ secrets.TELEGRAM_MAIN_CHAT_ID }}
      run: |
        cd Project
        python run_top5.py
```

## 🏠 Buyer Profiles

The application supports different buyer profiles for customized property scoring:

### Available Profiles
- `owner_occupier` (default) - Prefers newer, efficient homes with minimal renovation
- `diy_renovator` - Investment and renovation focus
- `growing_family` - Space and schools priority  
- `urban_professional` - Location and lifestyle
- `eco_conscious` - Energy efficiency focus
- `retiree` - Comfort and accessibility
- `budget_buyer` - Lowest price priority
- `default` - Balanced scoring

### Usage
```bash
# Use default profile (owner_occupier)
python run.py

# Use specific profile
python run.py --buyer-profile=growing_family

# Use persona enum shorthand
python run_top5.py --buyer-persona=owner_occupier

# Top5 with specific profile
python run_top5.py --buyer-profile=budget_buyer

# Scan deeper or faster
python run.py --deep-scan     # up to 20 pages/source (configurable)
python run.py --quick-scan    # skim ~4 pages/source for a quick refresh
```

## 📊 Usage

### Main Scraping
```bash
cd Project

# Run all scrapers (now ~12 pages/source by default)
python run.py

# Run with Telegram notifications
python run.py --send-to-telegram

# Run specific scraper only
python run.py --willhaben-only
python run.py --immo-kurier-only
python run.py --derstandard-only

# Run with specific buyer profile
python run.py --buyer-profile=urban_professional --send-to-telegram

# Deep dive for better offers
python run.py --deep-scan
```

### Top5 Properties Report
```bash
cd Project

# Run Top5 report
python run_top5.py

# Run with specific buyer profile
python run_top5.py --buyer-profile=retiree
```

### API Server
Dashboard uses Next.js API routes under `dashboard/app/api/`. The legacy Flask `Project/Api/` server has been removed.

## 🔍 Features

- **Multi-source scraping**: Willhaben, ImmoKurier, DerStandard
- **Intelligent scoring**: AI-powered property evaluation
- **Telegram integration**: Real-time notifications
- **Buyer profiles**: Customized scoring for different buyer types
- **Image handling**: Automatic image download and storage
- **MongoDB storage**: Robust data persistence
- **GitHub Actions ready**: Full CI/CD support

## 🏗️ Architecture

```
Project/
├── Application/
│   ├── main.py              # Main orchestration
│   ├── scoring.py           # Property scoring logic
│   ├── buyer_profiles.py    # Buyer profile definitions
│   ├── rating_calculator.py # Rating calculations
│   └── scraping/            # Scrapers
├── Integration/
│   ├── mongodb_handler.py   # Database operations
│   ├── telegram_bot.py      # Telegram integration
│   └── minio_handler.py     # Image storage
├── Domain/
│   ├── listing.py           # Data models
│   └── location.py          # Location utilities
└── UI/                      # Web interface
```

## 🧪 Testing

```bash
cd Tests

# Run all tests
python run_tests.py

# Test specific functionality
python test_github_actions_simple.py
python test_env_var_fallback.py
python test_buyer_profiles.py
```

## 📝 Configuration Priority

The application loads configuration in this order:
1. **config.json file** (if found)
2. **Environment variables** (override config.json values)
3. **Default values** (for missing configuration)

## 🔐 Security

- Sensitive data stored in GitHub Secrets
- Environment variable fallbacks for testing
- Graceful error handling for missing services

## 📈 Monitoring

- Comprehensive logging
- Telegram error notifications
- Performance metrics
- Data quality validation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. 
