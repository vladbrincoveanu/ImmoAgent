# Top5 Properties Report

This feature fetches the top 5 properties from MongoDB and sends them to the Telegram main channel.

## Features

- **Score-based ranking**: Properties are ranked by their AI-generated score
- **Configurable filters**: Minimum score, time range, and limit
- **Main.py style formatting**: Each property is sent as an individual message with emojis
- **Channel delivery**: Messages are sent to the ViennaApartmentsLive channel
- **No rankings**: Individual messages don't show rankings or scores (clean format)

## Configuration

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

### Parameters

- **`limit`**: Number of top properties to send (default: 5)
- **`min_score`**: Minimum score threshold (default: 40.0)
- **`days_old`**: Only consider properties from last N days (default: 7)
- **`excluded_districts`**: List of district codes to exclude (e.g., ["1100", "1160"])
- **`min_rooms`**: Minimum number of rooms required (default: 0 = no filter)
- **`include_monthly_payment`**: Whether to include monthly payment calculations (default: true)

### Filtering Features

#### District Exclusion
Exclude specific districts from the top5 results:
```json
"excluded_districts": ["1100", "1160"]
```

#### Minimum Rooms Filter
Only include properties with a minimum number of rooms:
```json
"min_rooms": 3  // Only 3+ room apartments
```

#### Monthly Payment Calculations
Each listing includes calculated monthly payments:
- **Loan Payment**: Monthly mortgage payment
- **Betriebskosten**: Operating costs
- **Total Monthly**: Combined monthly cost

The calculations are automatically added to each listing and displayed in Telegram messages.

## Usage

### Command Line

```bash
# From project root
cd Project
PYTHONPATH=. python run_top5.py

# Or with explicit Python path
PYTHONPATH=Project python Project/run_top5.py
```

### Programmatic Usage

```python
from Application.helpers.utils import load_config
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

# Load config
config = load_config()

# Initialize handlers
mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
telegram_bot = TelegramBot(
    config['telegram']['telegram_main']['bot_token'],
    config['telegram']['telegram_main']['chat_id']
)

# Fetch top listings
listings = mongo.get_top_listings(
    limit=5,
    min_score=40.0,
    days_old=7
)

# Send to Telegram
success = telegram_bot.send_top_listings(listings)
```

## Message Format

The Top5 report sends messages in the same format as `main.py`:

### Header Message
```
🏆 Top 5 Properties Report
📊 Found 15 total properties
🎯 Showing top 5 by score
📅 Generated at 2024-01-15 14:30:25
```

### Individual Property Messages
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

### Footer Message
```
✅ Sent 5/5 top properties to channel
```

## Key Differences from Old Format

| Old Format | New Format |
|------------|------------|
| Single long message | Multiple individual messages |
| Rankings (🥇🥈🥉) | No rankings |
| Scores displayed | No scores in individual messages |
| Separators between properties | Clean individual messages |
| All properties in one message | One property per message |
| **One long line** | **Multiple lines with proper formatting** |

## Recent Fixes

### Line Break Preservation (Latest)
- **Issue**: Messages were appearing as one long line instead of multiple lines
- **Cause**: The `clean_utf8_text` function was removing line breaks
- **Fix**: Modified the function to preserve line breaks while still cleaning whitespace
- **Result**: Each property detail now appears on its own line with proper formatting

## Integration

The Top5 feature integrates with:

- **MongoDB**: Fetches top-scored properties
- **Telegram**: Sends to main channel (ViennaApartmentsLive)
- **Scoring System**: Uses AI-generated scores for ranking
- **Configuration**: Respects score thresholds and time filters

## Testing

Run the formatting test to verify the new style:

```bash
python Tests/test_top5_formatting.py
```

This test verifies:
- ✅ Individual message formatting works
- ✅ Messages sent one by one (like main.py)
- ✅ No rankings or scores in individual messages
- ✅ Proper emojis and formatting 