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
  "telegram_bot_token": "your_bot_token",
  "telegram_chat_id": "your_chat_id",
  "max_pages": 5,
  "criteria": {
    "price_min": 200000,
    "price_max": 800000,
    "area_min": 40,
    "area_max": 120,
    "rooms_min": 2,
    "rooms_max": 4,
    "bezirk": ["1010", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090"]
  }
}
```

### 4. Run the Scraper

```bash
# Run all scrapers
python application/main.py

# Run specific scrapers only
python application/main.py --willhaben-only
python application/main.py --immo-kurier-only
python application/main.py --derstandard-only

# Skip image processing
python application/main.py --skip-images

# Only download/optimize images
python application/main.py --download-only
python application/main.py --optimize-only
```

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

### Notifications
- New property alerts with detailed information
- Daily summaries
- Error notifications (only errors, not all logs)
- System status updates

### Setup
1. Create a Telegram bot via @BotFather
2. Get your chat ID
3. Add credentials to `config.json`

## 🖼️ Image Management

### MinIO Storage
- **Automatic Upload**: Images downloaded from listings
- **Optimization**: Automatic resizing and compression
- **CDN-like**: Presigned URLs for fast access
- **Migration**: Script to move existing images

### Migration
```bash
python migrate_images_to_minio.py
```

## 🔧 Configuration

### Environment Variables
- `MONGO_URI`: MongoDB connection string
- `MINIO_ENDPOINT`: MinIO server endpoint
- `MINIO_ACCESS_KEY`: MinIO access key
- `MINIO_SECRET_KEY`: MinIO secret key

### Logging
- **Location**: `log/` directory
- **Files**: `immo-scouter.log`, `monitor.log`, `migration.log`
- **Telegram**: Only error logs sent to Telegram

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test suites
python tests/test_integration_accuracy.py
python tests/test_enhanced_scraper.py
python tests/test_main_integration.py
```

## 📈 Monitoring

### Log Files
- `log/immo-scouter.log`: Main application logs
- `log/monitor.log`: System monitoring logs
- `log/migration.log`: Image migration logs

### Health Checks
- MongoDB connectivity
- MinIO bucket access
- Telegram bot functionality
- Ollama model availability

## 🔄 Migration Guide

### From Local Images to MinIO
1. Run the migration script
2. Update templates to use MinIO URLs
3. Clean up local images (optional)

### From Old Logging to New Structure
- Logs now stored in `log/` directory
- Telegram only receives error logs
- Improved log formatting and organization

## 🛠️ Development

### Adding New Scrapers
1. Create scraper in `application/scraping/`
2. Implement required methods
3. Add to main orchestration
4. Update tests

### Adding New Data Sources
1. Update domain models if needed
2. Add data loading in helpers
3. Update scoring algorithms
4. Test integration

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For issues and questions:
- Check the logs in `log/` directory
- Review configuration in `config.json`
- Test individual components
- Check Docker service status

## 🔮 Roadmap

- [ ] Additional property sources
- [ ] Advanced filtering options
- [ ] Mobile app
- [ ] Machine learning price predictions
- [ ] Integration with real estate APIs
- [ ] Advanced analytics dashboard 