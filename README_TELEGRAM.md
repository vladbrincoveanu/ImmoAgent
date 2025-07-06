# Telegram Notifications for Property Monitor

This guide explains how to set up Telegram notifications for your property monitor to receive instant alerts when new matching properties are found.

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)
Run the setup script which will guide you through the process:

```bash
python setup_telegram.py
```

### Option 2: Manual Setup
Follow the steps below to manually configure Telegram notifications.

## 📋 Prerequisites

1. **Telegram Account**: You need a Telegram account
2. **Python**: Make sure you have Python 3.6+ installed
3. **Internet Connection**: For bot creation and testing

## 🔧 Step-by-Step Setup

### Step 1: Create a Telegram Bot

1. **Open Telegram** and search for `@BotFather`
2. **Send the command**: `/newbot`
3. **Choose a name** for your bot (e.g., "Property Monitor")
4. **Choose a username** (must end with 'bot', e.g., "property_monitor_bot")
5. **Save the bot token** that BotFather gives you (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

#### Option A: Send Message to Your Bot
1. Search for your bot by username in Telegram
2. Send any message to it (e.g., "Hello")
3. Visit this URL in your browser (replace with your bot token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for the `"chat"` → `"id"` field in the JSON response

#### Option B: Use @userinfobot
1. Search for `@userinfobot` in Telegram
2. Send `/start` to it
3. It will reply with your chat ID

### Step 3: Configure the Bot

1. **Edit** `telegram_config.json`:
   ```json
   {
       "enabled": true,
       "bot_token": "YOUR_BOT_TOKEN_HERE",
       "chat_id": "YOUR_CHAT_ID_HERE"
   }
   ```

2. **Replace** the placeholder values with your actual credentials

## 🧪 Testing the Setup

### Test Bot Connection
```bash
python setup_telegram.py
```
This will test if your bot can send messages to your chat.

### Test with Property Monitor
```bash
python main.py
```
This will run a single check and send notifications for any matching properties.

## 📱 Using Telegram Notifications

### Single Check
```bash
python main.py
```
- Runs one check of your search agent
- Sends Telegram notifications for matching properties
- Saves results to `filtered_listings.json`

### Continuous Monitoring
```bash
python monitor.py
```
- Runs continuous monitoring (checks every 5 minutes by default)
- Sends Telegram notifications for new matching properties
- Also sends desktop notifications and email (if configured)

### Cron Job Monitoring
```bash
python cron_check.py
```
- Designed for scheduled execution (e.g., every 15 minutes)
- Sends Telegram notifications for new matches
- Logs activity to `monitor.log`

## 📨 Message Format

When a matching property is found, you'll receive a formatted message like this:

```
🏠 NEW PROPERTY MATCH FOUND!

📍 Location: 1070 - Neubaugasse 15
💰 Price: €450,000
📐 Area: 75m²
💸 Price per m²: €6,000
🛏️ Rooms: 3
🚇 U-Bahn: 5 min walk
🏗️ Year Built: 1995
💳 Monthly Rate: €1,200

🔗 View Listing: [Link to Willhaben]

🎉 This property matches your criteria!
```

## ⚙️ Configuration Options

### Enable/Disable Notifications
Edit `telegram_config.json`:
```json
{
    "enabled": false  // Set to false to disable
}
```

### Customize Message Format
Edit `telegram_bot.py` and modify the `_format_property_message()` method to change the message format.

### Change Check Interval (Monitor Mode)
Edit `monitor.py` and change the `check_interval_minutes` parameter:
```python
monitor = RealTimeMonitor(alert_url, check_interval_minutes=10)  # Check every 10 minutes
```

## 🔍 Troubleshooting

### Bot Not Sending Messages
1. **Check bot token**: Make sure it's correct and complete
2. **Check chat ID**: Ensure it's the right format (usually a number)
3. **Start conversation**: Send a message to your bot first
4. **Check bot permissions**: Make sure the bot can send messages

### Common Error Messages
- `"Unauthorized"`: Invalid bot token
- `"Chat not found"`: Invalid chat ID
- `"Forbidden"`: Bot blocked or chat ID wrong

### Test Bot Manually
Visit this URL to test your bot (replace with your credentials):
```
https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Test
```

## 📊 Monitoring and Logs

### Log Files
- `monitor.log`: Contains detailed logs from the monitoring process
- `seen_listings.json`: Tracks previously seen listings to avoid duplicates
- `matches_YYYYMMDD.json`: Saves matching listings by date

### Statistics
The monitor tracks:
- Total checks performed
- Total listings found
- Matching listings count
- Last check time
- Start time

## 🔒 Security Notes

1. **Keep your bot token private** - don't share it publicly
2. **Don't commit** `telegram_config.json` to version control
3. **Use environment variables** for production deployments
4. **Regularly rotate** your bot token if needed

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your bot credentials
3. Test the bot manually using the Telegram API
4. Check the log files for error messages

## 🎯 Next Steps

Once Telegram notifications are working:
1. Set up continuous monitoring with `monitor.py`
2. Configure cron jobs for automated checking
3. Customize your property criteria in `criteria.json`
4. Set up email notifications as backup (optional) 