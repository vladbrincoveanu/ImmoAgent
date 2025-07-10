# Immo-Scouter: Vienna Real Estate Monitor

Immo-Scouter is a Python-based web scraping tool designed to monitor real estate listings from Willhaben, specifically for properties in Vienna. It automatically scrapes listings, filters them based on a rich set of user-defined criteria, calculates mortgage estimates, and sends instant notifications via Telegram for matching properties.

## Features

- **Continuous Monitoring**: Runs as a service to continuously check for new property listings.
- **Rich Filtering**: Filters properties based on price, area, rooms, location, construction year, energy class, and more.
- **Data Enrichment**: Uses an AI-powered analyzer (via Ollama) to extract structured data from unstructured listing descriptions, filling in missing details.
- **Geospatial Analysis**: Calculates walking distance to the nearest U-Bahn station and schools.
- **Mortgage Calculation**: Estimates monthly mortgage payments based on configurable down payment and interest rates.
- **Telegram Notifications**: Sends instant, detailed notifications for new matching properties.
- **Persistent Storage**: Uses MongoDB to store all scraped listings and track seen properties to avoid duplicates.
- **Docker Support**: Includes a `docker-compose.yml` for easy setup of MongoDB and Ollama services.

## Project Structure
```
immo-scouter/
├── data/                  # Data files (U-Bahn coordinates, schools)
├── tests/                 # Test scripts
├── backfill_missing_data.py # Script to enrich existing DB entries
├── config.default.json    # Default configuration file
├── crawl.py               # Core scraping logic
├── docker-compose.yml     # Docker setup for services
├── geocoding.py           # Geocoding and distance calculation
├── helpers.py             # Helper classes and functions
├── main.py                # Main script for a one-time scrape
├── mongodb_handler.py     # MongoDB interaction logic
├── monitor.py             # Continuous monitoring service
├── ollama_analyzer.py     # AI-based data extraction
├── requirements.txt       # Python dependencies
├── scrape.py              # Main scraper class
└── telegram_bot.py        # Telegram notification logic
```

## Setup Instructions

### 1. Prerequisites

- Python 3.9+
- Docker and Docker Compose

### 2. Create a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Navigate to the project directory
cd immo-scouter

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies

Install all required Python packages using pip.

```bash
pip install -r requirements.txt
```

### 4. Set Up Docker Services

The project relies on MongoDB and Ollama, which can be easily started using Docker Compose.

```bash
docker-compose up -d
```

This command will start two services in the background:
- `immo-mongo`: A MongoDB instance for data storage.
- `immo-ollama`: An Ollama instance for AI-based data analysis.

After starting Ollama for the first time, you may need to pull the model specified in `docker-compose.yml`.

### 5. Configure the Application

Create a `config.json` file by copying the default configuration.

```bash
cp config.default.json config.json
```

Now, edit `config.json` to match your preferences.

- **`criteria`**: This is the most important section. Define your filtering criteria here.
    - `price_per_m2_min`/`price_per_m2_max`: Price per square meter range.
    - `area_m2_min`: Minimum living area.
    - `rooms_min`: Minimum number of rooms.
    - `year_built_min`: Minimum construction year.
    - `ubahn_max_minutes`: Maximum walking time to the nearest U-Bahn.
    - `energy_class_min`: Minimum energy efficiency class (e.g., "D").
    - `down_payment_min`: Your planned down payment for mortgage calculation.
    - `interest_rate_max`: The interest rate for mortgage calculation.
- **`alert_url`**: The URL from your Willhaben search agent alert.
- **`telegram_bot_token` / `telegram_chat_id`**: Your Telegram bot credentials. See `setup_telegram.py` for instructions on how to get these.

#### Setting up Telegram Notifications

To receive notifications, you need to create a Telegram bot.

1.  **Create a bot**: Talk to `@BotFather` on Telegram and follow the instructions to create a new bot. You will receive a **bot token**.
2.  **Get your Chat ID**: Talk to `@userinfobot` on Telegram to get your user Chat ID.
3.  **Run the setup script**: Use the interactive script to test and save your credentials.
    ```bash
    python setup_telegram.py
    ```
    This will test your connection and update `config.json` for you.

## How to Run

### One-Time Scrape

To perform a single, comprehensive scrape based on your criteria, run `main.py`.

```bash
python main.py
```
This will scrape all pages of your search alert, filter the results, and save the matching listings to a JSON file.

### Continuous Monitoring

For continuous monitoring, run `monitor.py`. This script will periodically check for new listings and send Telegram notifications.

```bash
python monitor.py
```
This is the intended way to use the application for real-time alerts. It will run indefinitely until you stop it (Ctrl+C).

## Running Tests

To ensure everything is working correctly, you can run the suite of test scripts. The tests cover individual components, data extraction accuracy, and integration.

First, create a test runner script `run_tests.py`:

```python
#!/usr/bin/env python3
import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    # Discover and run all tests in the 'tests/' directory
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with a non-zero status code if any tests failed
    if not result.wasSuccessful():
        sys.exit(1)
```

Make it executable and run it:
```bash
chmod +x run_tests.py
./run_tests.py
```

This will execute all files starting with `test_` inside the `tests/` directory and provide a detailed report. 