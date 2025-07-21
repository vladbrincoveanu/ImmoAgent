# 🏠 Immo-Scouter - Vienna Real Estate Monitor

A comprehensive real estate monitoring system for Vienna, Austria. Scrapes multiple property websites, analyzes listings with AI, and provides notifications via Telegram.

## ✨ Features

- **Multi-Source Scraping**: Willhaben, Immo Kurier, and DerStandard
- **AI-Powered Analysis**: Uses Ollama for intelligent property scoring
- **MinIO Image Storage**: Scalable object storage for property images
- **Telegram Integration**: Real-time notifications and error reporting
- **MongoDB Database**: Robust data storage with deduplication
- **Web Interface**: Beautiful Flask-based UI for browsing properties
- **Parallel Processing**: Efficient multi-threaded scraping
- **Energy Efficiency Analysis**: HWB and energy class calculations
- **Infrastructure Proximity**: U-Bahn and school distance calculations
- **Top5 Reports**: Automated top property summaries
- **Flexible Telegram Control**: Optional Telegram notifications with `--send-to-telegram` flag

## 🏗️ Architecture

```
immo-scouter/
├── api/                    # Flask web API
├── application/           # Core application logic
│   ├── helpers/          # Utility functions and helpers
│   ├── scraping/         # Web scrapers for each source
│   └── main.py          # Main orchestration logic
├── domain/               # Data models and domain logic
├── integration/          # External service integrations
│   ├── mongodb_handler.py
│   ├── minio_handler.py
│   └── telegram_bot.py
├── UI/                   # UI assets and templates
│   ├── static/          # Static web assets (css, images, js)
│   └── templates/       # Web UI templates
├── data/                # Data files (schools, U-Bahn stations)
├── log/                 # Application logs
└── tests/               # Test suite
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- MongoDB (via Docker)
- MinIO (via Docker)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd immo-scouter
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start Services

```bash
docker-compose up -d
```

This starts:
- **MongoDB** (port 27017)
- **MinIO** (port 9000, console 9001)
- **Ollama** (port 11434)

### 3. Configure

Create `config.json` in the project root:

```json
{
  "mongodb_uri": "mongodb://admin:admin@localhost:27017/immo?authSource=admin",
  "openai_api_key": "your-openai-api-key",
  "openai_model": "gpt-4o-mini",
  "max_pages": 5,
  "scraping": {
    "timeout": 30,
    "delay_between_requests": 1,
    "selenium_wait_time": 10
  },
  "telegram": {
    "telegram_main": {
      "bot_token": "your-main-bot-token",
      "chat_id": "your-main-chat-id"
    },
    "telegram_dev": {
      "bot_token": "your-dev-bot-token", 
      "chat_id": "your-dev-chat-id"
    },
    "min_score_threshold": 40
  },
  "top5": {
    "limit": 5,
    "min_score": 40.0,
    "days_old": 7,
    "excluded_districts": ["1100", "1160"],
    "min_rooms": 3,
    "include_monthly_payment": true
  },
  "criteria": {
    "price_max": 1000000,
    "price_per_m2_max": 20000,
    "area_m2_min": 20,
    "rooms_min": 3,
    "year_built_min": 1970,
    "districts": ["1010", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090"]
  }
}
```

### 4. Run the Scraper

```bash
# Run all scrapers (no Telegram notifications by default)
python run.py

# Run with Telegram notifications enabled
python run.py --send-to-telegram

# Run specific scrapers only
python run.py --willhaben-only
python run.py --immo-kurier-only
python run.py --derstandard-only

# Skip image processing
python run.py --skip-images

# Only download/optimize images
python run.py --download-only
python run.py --optimize-only

# Combine flags
python run.py --send-to-telegram --willhaben-only
python run.py --send-to-telegram --skip-images
```

> **Note**: By default, Telegram notifications are disabled. Use `--send-to-telegram` flag to enable them.

### 5. Access Web Interface

```bash
python api/app.py
```

Visit `http://localhost:5001` to browse properties.

## 📊 Data Sources

### Willhaben
- **URL**: https://www.willhaben.at
- **Features**: Comprehensive property listings, detailed filters
- **Data**: Price, area, rooms, energy info, images

### Immo Kurier
- **URL**: https://www.immokurier.at
- **Features**: Professional real estate listings
- **Data**: Detailed property information, energy certificates

### DerStandard
- **URL**: https://immobilien.derstandard.at
- **Features**: Newspaper-based listings
- **Data**: Quality listings with editorial oversight

## 🗄️ Data Storage

### MongoDB
- **Database**: `immo`
- **Collection**: `listings`
- **Features**: Deduplication, indexing, flexible schema

### MinIO
- **Bucket**: `property-images`
- **Features**: Image optimization, presigned URLs, scalable storage
- **Access**: http://localhost:9001 (admin/minioadmin123)

## 🤖 AI Integration

### Ollama
- **Model**: qwen2.5-coder:7b
- **Purpose**: Property scoring and analysis
- **Features**: Local inference, no external API calls

### Property Scoring
The system calculates a comprehensive score based on:
- Price per square meter
- Location quality (district, transport proximity)
- Energy efficiency
- Property condition
- Infrastructure proximity

## 📱 Telegram Integration

### Dual Channel System

The system uses two Telegram channels:

1. **Main Channel**: Receives only high-score properties (score > 40)
   - Property details with images
   - Price, area, location, and analysis
   - Direct links to listings

2. **Dev Channel**: Receives logs and error messages
   - Scraping progress updates
   - Error notifications
   - System status messages

### Telegram Flag Control

The `--send-to-telegram` flag controls whether property notifications are sent to Telegram. **By default, Telegram notifications are disabled** to prevent unwanted messages.

#### Default Behavior (No Telegram)
```bash
# Run scraper without sending to Telegram
python run.py

# Run with other flags, still no Telegram
python run.py --skip-images
python run.py --willhaben-only
```

#### Enable Telegram Notifications
```bash
# Run scraper and send to Telegram
python run.py --send-to-telegram

# Combine with other flags
python run.py --send-to-telegram --skip-images
python run.py --send-to-telegram --willhaben-only
```

#### What Happens

**When `--send-to-telegram` is NOT used (default):**
- ✅ Scraping runs normally
- ✅ Properties are saved to MongoDB with scores
- ✅ Images are downloaded (unless `--skip-images` is used)
- ❌ **No Telegram notifications are sent**
- ❌ **No Telegram summary is sent**
- ❌ **No "no results" Telegram message is sent**

**When `--send-to-telegram` is used:**
- ✅ Scraping runs normally
- ✅ Properties are saved to MongoDB with scores
- ✅ Images are downloaded (unless `--skip-images` is used)
- ✅ **High-score properties are sent to Telegram**
- ✅ **Summary is sent to Telegram**
- ✅ **"No results" message is sent if no properties found**

### Setup
1. Create a Telegram bot via @BotFather
2. Get your chat ID
3. Add credentials to `config.json`

## 🏆 Top5 Properties Report

This feature fetches the top 5 properties from MongoDB and sends them to the Telegram main channel.

### Features
- **Score-based ranking**: Properties are ranked by their AI-generated score
- **Configurable filters**: Minimum score, time range, and limit
- **Main.py style formatting**: Each property is sent as an individual message with emojis
- **Channel delivery**: Messages are sent to the ViennaApartmentsLive channel
- **No rankings**: Individual messages don't show rankings or scores (clean format)

### Configuration
Add the following section to your `config.json`:

```json
{
  "top5": {
    "limit": 5,
    "min_score": 40.0,
    "days_old": 7,
    "excluded_districts": ["1100", "1160"],
    "min_rooms": 3,
    "include_monthly_payment": true
  }
}
```

### Usage
```bash
# From project root
cd Project
PYTHONPATH=. python run_top5.py

# Or with explicit Python path
PYTHONPATH=Project python Project/run_top5.py
```

### Message Format

The Top5 report sends messages in the same format as `main.py`:

#### Header Message
```
🏆 Top 5 Properties Report
📊 Found 15 total properties
🎯 Showing top 5 by score
📅 Generated at 2024-01-15 14:30:25
```

#### Individual Property Messages
Each property is sent as a separate message with emojis:

```
🏠 <b>Stipcakgasse 12, 1230 Wien</b> - €280,000
💰 Rate: €1,134 (€56,000 initial sum invested)
📄 Betriebskosten: €248 (est.)
💳 Total Monthly: €1,382 (€1,134 loan + €248 BK)
📍 1230
📐 48.13m² - €5,818/m²
🛏️ 2.0 Zimmer
🚇 U-Bahn: 12 min
🏫 Schule: 10 min
🏗️ Baujahr: 2024
🔧 Zustand: Erstbezug
⚡ Energieklasse: A
🔗 <a href='https://example.com'>Zur Anzeige</a>
```

## 🖼️ Image Management

### MinIO Storage
- **Automatic Upload**: Images downloaded from listings
- **Optimization**: Automatic resizing and compression
- **CDN-like**: Presigned URLs for fast access

## ⚙️ Configuration Management

### Configuration Files

#### 1. Main Configuration: `config.json` (Root Directory)
**Location**: `/config.json` (in the project root directory)
**Purpose**: Production configuration used by the main application

#### 2. Default Configuration Template: `config.json.default`
**Location**: `/config.json.default` (in the project root directory)
**Purpose**: Template file for new installations

#### 3. Test Configuration: `Tests/test_config.json`
**Location**: `/Tests/test_config.json`
**Purpose**: Configuration for testing with safe, non-production values

### Configuration Loading Logic

The application uses a smart configuration loading system:

1. **Project Root Detection**: The `get_project_root()` function finds the project root
2. **Configuration Loading Priority**: Loads `{project_root}/config.json` first, then fallbacks
3. **Test Configuration**: When running tests, uses `Tests/test_config.json`

### Environment Variables

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

### Telegram Chat Types

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

## 🧪 Testing

Run the test suite:
```bash
pytest Tests/ --maxfail=3 --disable-warnings -v
```

Run specific tests:
```bash
# Test Immo Kurier scraper
python Tests/test_immo_kurier_fixed.py

# Test integration
pytest Tests/test_comprehensive_integration.py -v

# Test Telegram flag
python Tests/test_telegram_flag.py

# Test logging fix
python Tests/test_logging_fix.py
```

## 📈 Monitoring

The system provides comprehensive logging:
- Scraping progress and results
- AI analysis scores
- Database operations
- Telegram notifications
- Error tracking

Logs are written to `log/immo-scouter.log`

## 🔧 Development

### Adding a New Scraper

1. Create a new scraper class in `Project/Application/scraping/`
2. Implement the required methods:
   - `scrape_search_results()`
   - `scrape_single_listing()`
3. Add to `main.py` integration
4. Create tests in `Tests/`

### Extending Analysis

The AI analysis can be customized by modifying:
- `Project/Application/analyzer.py`
- Criteria in `config.json`
- Scoring algorithms

## 🚀 Production Deployment

### Quick Deployment
```bash
cd Project
./deploy.sh
```

### Manual Docker Deployment
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
```

### Production Features
- ✅ **User Authentication** - Secure login system with user management
- ✅ **HTTPS/SSL** - Encrypted connections with automatic redirects
- ✅ **Rate Limiting** - Protection against abuse and DDoS
- ✅ **Security Headers** - XSS, CSRF, and clickjacking protection
- ✅ **Load Balancing** - Nginx reverse proxy with caching
- ✅ **Health Checks** - Automatic service monitoring and restart
- ✅ **Comprehensive Logging** - Application and access logs
- ✅ **Persistent Storage** - MongoDB and MinIO with backup-ready volumes
- ✅ **Auto-scaling Ready** - Containerized architecture for easy scaling

### Default Credentials
- **Admin Username**: `admin`
- **Admin Password**: `admin123` (change in production!)
- **MinIO Console**: http://localhost:9001
- **Application**: http://localhost:5001

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the logs in `log/immo-scouter.log`
2. Review the test suite for examples
3. Check the configuration in `config.json`
4. Open an issue on GitHub

## 🔄 Updates

The system automatically:
- Deduplicates listings by URL
- Updates existing listings with new data
- Maintains historical data in MongoDB
- Optimizes images for storage

## 🔒 Security Best Practices

1. **Never commit real credentials** to version control
2. **Use environment variables** for sensitive data
3. **Use test configuration** for automated tests
4. **Keep production config** separate from development
5. **Regularly rotate** API keys and tokens

## 🐛 Troubleshooting

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

4. **"No such file or directory: log/immo-scouter.log"**
   - The log directory is created automatically
   - Check file permissions
   - Ensure the application has write access

### Debug Configuration Loading

```python
from Application.helpers.utils import get_project_root, load_config

# Check project root
print(f"Project root: {get_project_root()}")

# Load and inspect config
config = load_config()
print(f"Config keys: {list(config.keys())}")
```

---

**Happy House Hunting! 🏠✨** 