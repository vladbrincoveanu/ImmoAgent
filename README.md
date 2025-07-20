# 🏠 Immo-Scouter

A comprehensive real estate scraping and analysis system for Vienna, Austria. Automatically scrapes property listings from multiple sources, analyzes them using AI, and sends high-quality matches to Telegram.

## 🚀 Features

- **Multi-Source Scraping**: Willhaben, Immo Kurier, and DerStandard
- **AI-Powered Analysis**: Uses OpenAI GPT models for intelligent property scoring
- **Dual Telegram Channels**: Main channel for high-score properties, dev channel for logs
- **MongoDB Integration**: Persistent storage with deduplication
- **Image Processing**: Automatic image download and optimization
- **Comprehensive Testing**: Full test suite with real data validation

## 📋 Requirements

- Python 3.8+
- MongoDB
- OpenAI API key (optional, for AI analysis)
- Telegram bot tokens (for notifications)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd immo-scouter
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r Project/requirements.txt
   ```

4. **Set up MongoDB**
   ```bash
   # Using Docker
   docker-compose up -d
   
   # Or install MongoDB locally
   # Follow MongoDB installation guide for your OS
   ```

5. **Configure the application**
   ```bash
   # Copy the default config
   cp config.json.default config.json
   
   # Edit config.json with your settings
   nano config.json
   ```

## ⚙️ Configuration

Create a `config.json` file in the root directory:

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
  "criteria": {
    "price_max": 1000000,
    "price_per_m2_max": 20000,
    "area_m2_min": 20,
    "rooms_min": 1,
    "districts": ["1010", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090", "1100", "1110", "1120", "1130", "1140", "1150", "1160", "1170", "1180", "1190", "1200", "1210", "1220", "1230"]
  }
}
```

### Configuration Options

- **`mongodb_uri`**: MongoDB connection string
- **`openai_api_key`**: OpenAI API key for AI analysis (optional)
- **`openai_model`**: OpenAI model to use (default: gpt-4o-mini)
- **`max_pages`**: Maximum pages to scrape per source
- **`telegram`**: Telegram bot configuration
  - `telegram_main`: Main channel for high-score properties
  - `telegram_dev`: Dev channel for logs and errors
  - `min_score_threshold`: Minimum score for main channel (default: 40)
- **`criteria`**: Property filtering criteria
  - `price_max`: Maximum price in EUR
  - `price_per_m2_max`: Maximum price per m²
  - `area_m2_min`: Minimum area in m²
  - `rooms_min`: Minimum number of rooms
  - `districts`: Allowed Vienna districts (4-digit codes)

## 📸 Screenshots

Here's a glimpse of the Immo-Scouter interface, showcasing property listings with their scores and details:

![Immo-Scouter Property Listings Grid](images/properties_grid.png)

The interface displays a grid of property cards with:
- **AI-generated scores** (55, 54, 53, etc.) in green badges
- **Price information** in Euros (€207,000, €348,900, etc.)
- **Key metrics**: area, rooms, price/m², energy class, monthly costs
- **Infrastructure details**: U-Bahn distance, school distance, HWB values
- **Source indicators**: willhaben, immo_kurier, derstandard
- **Clean, professional design** with easy-to-read property cards

## 🚀 Usage

### Development Mode

#### Run All Sources
```bash
PYTHONPATH=Project python Project/Application/main.py
```

#### Run Specific Source
```bash
# Willhaben only
PYTHONPATH=Project python Project/Application/main.py --willhaben-only

# Immo Kurier only  
PYTHONPATH=Project python Project/Application/main.py --immo-kurier-only

# DerStandard only
PYTHONPATH=Project python Project/Application/main.py --derstandard-only
```

#### Skip Image Processing
```bash
PYTHONPATH=Project python Project/Application/main.py --skip-images
```

#### Run Development API Server
```bash
cd Project
python run_api.py
```

### Production Mode

#### Quick Deployment
```bash
cd Project
./deploy.sh
```

#### Manual Docker Deployment
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
```

#### Production Features
- ✅ **User Authentication** - Secure login system with user management
- ✅ **HTTPS/SSL** - Encrypted connections with automatic redirects
- ✅ **Rate Limiting** - Protection against abuse and DDoS
- ✅ **Security Headers** - XSS, CSRF, and clickjacking protection
- ✅ **Load Balancing** - Nginx reverse proxy with caching
- ✅ **Health Checks** - Automatic service monitoring and restart
- ✅ **Comprehensive Logging** - Application and access logs
- ✅ **Persistent Storage** - MongoDB and MinIO with backup-ready volumes
- ✅ **Auto-scaling Ready** - Containerized architecture for easy scaling

#### Default Credentials
- **Admin Username**: `admin`
- **Admin Password**: `admin123` (change in production!)
- **MinIO Console**: http://localhost:9001
- **Application**: http://localhost:5001

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
```

## 📊 Telegram Notifications

The system uses two Telegram channels:

1. **Main Channel**: Receives only high-score properties (score > 40)
   - Property details with images
   - Price, area, location, and analysis
   - Direct links to listings

2. **Dev Channel**: Receives logs and error messages
   - Scraping progress updates
   - Error notifications
   - System status messages

## 🏗️ Architecture

```
immo-scouter/
├── Project/
│   ├── Application/
│   │   ├── scraping/          # Scrapers for each source
│   │   ├── analyzer.py        # AI-powered analysis
│   │   └── main.py           # Main orchestration
│   ├── Domain/
│   │   ├── listing.py        # Data models
│   │   └── sources.py        # Source enums
│   ├── Integration/
│   │   ├── mongodb_handler.py # Database operations
│   │   ├── telegram_bot.py   # Telegram integration
│   │   └── minio_handler.py  # Image storage
│   └── UI/                   # Web interface
├── Tests/                    # Test suite
├── config.json              # Configuration
└── README.md               # This file
```

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

## 📈 Monitoring

The system provides comprehensive logging:
- Scraping progress and results
- AI analysis scores
- Database operations
- Telegram notifications
- Error tracking

Logs are written to `log/immo-scouter.log`

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

---

**Happy House Hunting! 🏠✨** 