# Top 5 Properties Report

This feature allows you to fetch the top 5 (or configurable number) of properties from MongoDB and send them to the Telegram main channel as a formatted report.

## Features

- 🏆 **Ranked Properties**: Properties are ranked by score (highest first)
- 📊 **Configurable Parameters**: Adjust limit, minimum score, and time range
- 📱 **Telegram Integration**: Sends formatted reports to Telegram main channel
- 🎯 **Smart Filtering**: Only includes properties from recent days with minimum score
- 📝 **Detailed Formatting**: Includes ranking, scores, prices, areas, and property links

## Configuration

Add the following section to your `config.json`:

```json
{
  "top5": {
    "limit": 5,
    "min_score": 40.0,
    "days_old": 7
  }
}
```

### Parameters

- **`limit`**: Maximum number of properties to include in the report (default: 5)
- **`min_score`**: Minimum score threshold for properties to be included (default: 40.0)
- **`days_old`**: Only include properties from the last N days (default: 7)

## Usage

### Running the Report

```bash
cd Project
python run_top5.py
```

### Expected Output

The script will:
1. Connect to MongoDB
2. Fetch top properties matching criteria
3. Send formatted report to Telegram main channel
4. Display summary in console

### Console Output Example

```
🏆 Starting Top 5 Properties Report
==================================================
📊 Fetching top 5 listings...
🎯 Minimum score: 40.0
📅 Last 7 days
✅ Successfully sent top 5 listings to Telegram

📊 Summary:
  1. Score: 48.8 | €600,000 | 70m² | 3 rooms | 1030 | derstandard
  2. Score: 48.3 | €398,000 | 116m² | 3 rooms | 1100 | derstandard
  3. Score: 47.7 | €719,000 | 194m² | 3 rooms | 1160 | derstandard
  4. Score: 45.6 | €498,000 | 103m² | 3 rooms | 1040 | derstandard
  5. Score: 44.8 | €549,000 | 127m² | 3 rooms | 1100 | derstandard
```

### Telegram Message Format

The Telegram message will include:
- 🏆 Title with ranking
- 📊 Summary statistics
- 🥇🥈🥉 Ranking emojis for top 3
- 📝 Property details (price, area, rooms, district)
- 🔗 Direct links to property listings
- 📅 Timestamp

## Testing

### Test MongoDB Functionality Only

```bash
python Tests/test_top5_mongodb_only.py
```

### Test Full Functionality (requires Telegram config)

```bash
python Tests/test_top5_functionality.py
```

## Integration

### Programmatic Usage

You can also use the functionality programmatically:

```python
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

# Initialize handlers
mongo = MongoDBHandler(uri="mongodb://localhost:27017/")
telegram_bot = TelegramBot(bot_token, chat_id)

# Fetch top listings
listings = mongo.get_top_listings(limit=5, min_score=40.0, days_old=7)

# Send to Telegram
success = telegram_bot.send_top_listings(listings, "🏆 Top Properties Report")
```

### Cron Job Setup

To run the report automatically, you can set up a cron job:

```bash
# Run daily at 9 AM
0 9 * * * cd /path/to/Project && python run_top5.py

# Run weekly on Sunday at 10 AM
0 10 * * 0 cd /path/to/Project && python run_top5.py
```

## Troubleshooting

### Common Issues

1. **No listings found**: Check if there are properties in MongoDB with scores above the threshold
2. **Telegram connection failed**: Verify bot token and chat ID in config
3. **MongoDB connection failed**: Ensure MongoDB is running and accessible

### Logs

Check the log file for detailed information:
```
Project/log/top5.log
```

## Dependencies

- MongoDB connection
- Telegram bot configuration
- Python packages: `pymongo`, `requests`, `logging`

## Files

- `run_top5.py` - Main script to run the report
- `Integration/mongodb_handler.py` - MongoDB operations
- `Integration/telegram_bot.py` - Telegram messaging
- `Tests/test_top5_*.py` - Test scripts
- `config.json` - Configuration file 