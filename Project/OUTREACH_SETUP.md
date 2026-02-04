# Outreach Email Setup Guide

## 🔒 Security Best Practice

**⚠️ CRITICAL: Never store passwords in `config.json` or commit them to git!**

- ✅ **DO**: Use environment variables (`SMTP_PASSWORD`)
- ✅ **DO**: Use `.env` file (already in `.gitignore`)
- ✅ **DO**: Use secrets management in cloud/CI environments
- ❌ **DON'T**: Put passwords in `config.json`
- ❌ **DON'T**: Commit `.env` files (already ignored)
- ❌ **DON'T**: Hardcode passwords in code

The `.gitignore` file already excludes:
- `.env` and `.env.*` files
- `config.json` (may contain sensitive data)

## Quick Setup

1. **Set environment variables** (choose one method):

   **Option A: Export in terminal (temporary)**
   ```bash
   export SMTP_USER="your-email@gmail.com"
   export SMTP_PASSWORD="your-app-password"
   export SENDER_EMAIL="your-email@gmail.com"
   export SENDER_NAME="Your Name"
   ```

   **Option B: Create `.env` file** (recommended for local development)
   ```bash
   # Create .env file in project root
   cat > .env << EOF
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SENDER_EMAIL=your-email@gmail.com
   SENDER_NAME=Your Name
   EOF
   ```
   
   Then load it before running:
   ```bash
   export $(cat .env | xargs)
   python3 Project/run_outreach.py --test-smtp
   ```

   **Option C: Use system environment variables** (recommended for production)
   - Set in your system's environment (systemd, Docker, cloud platform, etc.)

2. **For Gmail users:**
   - Go to https://myaccount.google.com/apppasswords
   - Enable 2-Factor Authentication if not already enabled
   - Generate an App Password for "Mail"
   - Use that 16-character password (not your regular Gmail password)

3. **Update `config.json`:**
   ```json
   "outreach": {
       "enabled": true,
       "smtp_provider": "gmail",
       "smtp_user": "your-email@gmail.com",
       "smtp_password": null,  // ← Leave as null, will use env var
       "sender_email": "your-email@gmail.com",
       "sender_name": "Your Name"
   }
   ```

## Environment Variables

The system will automatically use these environment variables if set:

- `SMTP_USER` - Your SMTP username (email address)
- `SMTP_PASSWORD` - Your SMTP password (App Password for Gmail)
- `SMTP_HOST` - Optional: Override SMTP host (defaults based on provider)
- `SMTP_PORT` - Optional: Override SMTP port (default: 587)
- `SENDER_EMAIL` - Email address to send from
- `SENDER_NAME` - Display name for sender

## Testing

```bash
# Test SMTP connection
python3 Project/run_outreach.py --test-smtp

# Dry run (preview emails without sending)
python3 Project/run_outreach.py --dry-run --limit=2

# Actually send emails
python3 Project/run_outreach.py --limit=5
```

## Security Notes

- ✅ `.env` files are already in `.gitignore`
- ✅ Environment variables take precedence over `config.json`
- ✅ Never commit passwords to git
- ✅ Use App Passwords for Gmail (not your main password)

