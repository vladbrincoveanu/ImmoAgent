# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Immo-Scouter is a comprehensive real estate scraping and analysis system for Vienna, Austria. It scrapes property listings from multiple sources (Willhaben, ImmoKurier, DerStandard), scores them using configurable buyer profiles, and sends notifications via Telegram.

## Core Commands

### Running the Main Scraper
```bash
cd Project
python run.py                              # Standard scrape (~12 pages/source)
python run.py --send-to-telegram          # Scrape + send results to Telegram
python run.py --deep-scan                 # Deep scrape (~20 pages/source)
python run.py --quick-scan                # Quick scrape (~4 pages/source)
python run.py --willhaben-only            # Scrape specific source only
python run.py --buyer-profile=owner_occupier  # Use specific buyer profile
```

### Top 5 Properties Report
```bash
cd Project
python run_top5.py                        # Send top 5 listings to Telegram
python run_top5.py --limit=10             # Top N listings
python run_top5.py --weekly               # Weekly digest mode (top 10, allow resends)
python run_top5.py --buyer-profile=retiree  # Use specific buyer profile
python run_top5.py --min-score=30.0       # Minimum score threshold
```

### Outreach System
```bash
cd Project
python run_outreach.py --test-smtp        # Test SMTP connection
python run_outreach.py --dry-run --limit=2  # Preview emails without sending
python run_outreach.py --limit=5          # Send offer emails to top 5 listings
python run_outreach.py --discount=25      # Override default discount percentage
```

### Full Pipeline
```bash
# Run scraper + send top 5 report
bash Project/run_full_pipeline.sh
bash Project/run_full_pipeline.sh --max-pages 1 --willhaben-only
```

### Testing
```bash
cd Tests
python run_tests.py                       # Run all tests
python test_buyer_profiles.py            # Test specific functionality
python test_github_actions_simple.py
```

### API Server
```bash
cd Project
python run_api.py                        # Start Flask API server
```

## Architecture

### Module Structure

The codebase follows a domain-driven design with clear separation:

**Project/Application/** - Core business logic
- `main.py` - Main orchestration, scraping coordination, image download
- `scoring.py` - Property scoring system with configurable weights
- `buyer_profiles.py` - Buyer persona definitions and weight profiles
- `rating_calculator.py` - Rating calculations for properties
- `analyzer.py` - Structured analysis using OpenAI/Ollama
- `scraping/` - Source-specific scrapers (Willhaben, ImmoKurier, DerStandard)
- `outreach/` - Email outreach system (contact extraction, email sending)

**Project/Integration/** - External services
- `mongodb_handler.py` - MongoDB operations, listing CRUD, duplicate detection
- `telegram_bot.py` - Telegram notifications and formatting
- `minio_handler.py` - Image storage (MinIO)

**Project/Domain/** - Data models
- `listing.py` - Property listing dataclass
- `location.py` - Location utilities
- `sources.py` - Data source definitions

**Project/UI/** - Web interface (Flask-based)

**Tests/** - Comprehensive test suite

### Key Data Flow

1. **Scraping Pipeline** (`run.py` → `Application.main`)
   - Each scraper (`*_scraper.py`) fetches listings from source
   - Listings are validated using `listing_validator.py`
   - Duplicates are detected via MongoDB URL/hash checking
   - Images are downloaded and stored (local or MinIO)
   - Listings are scored using buyer profiles
   - Results stored in MongoDB

2. **Top 5 Report** (`run_top5.py`)
   - Fetches all listings from MongoDB
   - Filters and validates (removes broken URLs)
   - Scores using current buyer profile
   - Selects top N based on score
   - Sends formatted messages to Telegram
   - Tracks sent listings to avoid duplicates

3. **Outreach System** (`run_outreach.py`)
   - Fetches top scored listings
   - Extracts contact info from listing pages
   - Generates personalized offer emails (German)
   - Sends via SMTP with configurable discount
   - Tracks sent emails in MongoDB

## Buyer Profiles System

The scoring system supports different buyer personas with custom weight distributions:

- `default` - Balanced scoring
- `owner_occupier` - Prioritizes newer, efficient homes with minimal renovation
- `diy_renovator` - Investment and renovation focus
- `growing_family` - Space and schools priority
- `urban_professional` - Location and lifestyle
- `eco_conscious` - Energy efficiency focus
- `retiree` - Comfort and accessibility
- `budget_buyer` - Lowest price priority

Scoring criteria and weights are defined in:
- `buyer_profiles.py` - Profile definitions
- `scoring.py` - Normalization ranges and scoring logic

## Configuration

### Priority Order
1. `config.json` file (if found)
2. Environment variables (override config.json)
3. Default values

### Required Environment Variables (for GitHub Actions/Production)
```bash
MONGODB_URI=mongodb://user:pass@host:port/db
TELEGRAM_MAIN_BOT_TOKEN=your_bot_token
TELEGRAM_MAIN_CHAT_ID=your_chat_id
```

### Optional Environment Variables
```bash
TELEGRAM_BOT_VIENNA_TOKEN, TELEGRAM_BOT_VIENNA_CHAT_ID
OLLAMA_BASE_URL, OLLAMA_MODEL
OPENAI_API_KEY, OPENAI_MODEL
MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET_NAME
SMTP_USER, SMTP_PASSWORD, SENDER_EMAIL, SENDER_NAME
```

### Security - NEVER Commit Secrets
- `.env` files are in `.gitignore`
- `config.json` is in `.gitignore`
- Outreach SMTP passwords MUST use environment variables
- For Gmail: Use App Passwords (see `Project/SETUP_GMAIL.md`)
- Never set `smtp_password` in `config.json` - always use `SMTP_PASSWORD` env var

## Important Implementation Details

### MongoDB Schema
Listings are stored with:
- Deduplication via `url` and `url_hash` fields
- `sent_to_telegram` flag to prevent duplicate notifications
- `sent_outreach_at` timestamp for outreach tracking
- Scoring fields: `total_score`, `score_breakdown`, `buyer_profile`
- URL validation: `url_is_valid` boolean flag

### Scraper Behavior
- Each scraper implements its own page navigation and parsing
- Uses Selenium for dynamic content
- Implements rate limiting and retries
- Validates listings before storage
- Stores original URLs for deduplication

### Listing Validation
The `listing_validator.py` module:
- Checks for required fields (title, url, price, location)
- Validates URL accessibility (HTTP 200 check)
- Marks invalid listings in MongoDB
- Used by run_top5.py to filter out broken listings

### Image Handling
- Images can be stored locally or in MinIO (S3-compatible)
- Automatic download and optimization (if PIL available)
- Path stored in `minio_image_path` or `image_path` field

### Telegram Integration
- Supports multiple bot configurations (main, dev, vienna)
- Formatted messages with property details
- Inline keyboard buttons for listing URLs
- Handles long messages (4096 char limit)

## Common Development Workflows

### Adding a New Scraper
1. Create `Project/Application/scraping/new_source_scraper.py`
2. Implement scraping logic following existing patterns
3. Add to `Application.main.py` orchestration
4. Test with isolated script first
5. Add command-line flag (e.g., `--new-source-only`)

### Adding a New Buyer Profile
1. Add profile to `BUYER_PROFILES` dict in `buyer_profiles.py`
2. Ensure weights sum to 1.0
3. Add to `BuyerPersona` enum if using enum shortcuts
4. Test with `python show_profiles.py`

### Modifying Scoring Weights
- Edit `NORMALIZATION_RANGES` in `scoring.py` to adjust score ranges
- Edit buyer profile weights in `buyer_profiles.py`
- Use `validate_weights()` to ensure weights sum to 1.0

### Testing Configuration
- Use `Tests/test_config.json` for test-specific config
- Set test environment variables before running tests
- Mock external services (MongoDB, Telegram) when appropriate

## CI/CD Integration

The system is designed for GitHub Actions:
- Environment variables override config.json
- No local file dependencies
- Graceful degradation if services unavailable
- Comprehensive error handling and logging

See README.md for example GitHub Actions workflow.

## File Locations

- Logs: `Project/log/`
- Temporary files: Use scratchpad directory, not `/tmp`
- Config: `config.json` (in repo root or Project/)
- Data files: `Project/data/` (vienna_schools.json, ubahn_coordinates.json)

## Key Dependencies

- `pymongo` - MongoDB operations
- `selenium` + `webdriver-manager` - Web scraping
- `python-telegram-bot` - Telegram integration
- `beautifulsoup4` - HTML parsing
- `torch` + `transformers` - AI analysis (optional)
- `minio` - Image storage (optional)
- `flask` - API server
- `requests` - HTTP client
- `python-dotenv` - Environment variable management

## Notes for Claude Code

1. **Run.py path**: Use `python Project/run.py` from repo root OR `python run.py` from Project/ directory
2. **Config search**: Scripts automatically search multiple paths for `config.json`
3. **Buyer profiles**: Can use string keys OR `BuyerPersona` enum members
4. **Scoring changes**: Always validate weights sum to 1.0 after modifications
5. **MongoDB queries**: Use `mongodb_handler.py` methods, don't write raw queries
6. **Telegram formatting**: Follow existing patterns in `telegram_bot.py` for message formatting
7. **URL validation**: Always use `listing_validator.py` before sending listings to users
8. **Outreach emails**: Templates are in German, located in `outreach/email_sender.py`
