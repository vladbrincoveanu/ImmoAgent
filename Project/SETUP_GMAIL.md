# Gmail App Password Setup Guide

## Step 1: Enable 2-Factor Authentication

1. Go to https://myaccount.google.com/security
2. Under "Signing in to Google", click **2-Step Verification**
3. Follow the prompts to enable 2FA (if not already enabled)

## Step 2: Create App Password

1. Go to https://myaccount.google.com/apppasswords
   - Or: Google Account → Security → 2-Step Verification → App passwords
2. Select app: **Mail**
3. Select device: **Other (Custom name)**
4. Enter name: `Immo-Scouter` (or any name you like)
5. Click **Generate**
6. **Copy the 16-character password** (it looks like: `abcd efgh ijkl mnop`)
   - ⚠️ You'll only see this once! Save it immediately.

## Step 3: Set Environment Variable (REQUIRED - Never commit passwords!)

⚠️ **SECURITY WARNING**: Never put passwords in `config.json` or commit them to git!
Always use environment variables or secrets management.

**Option A: Create .env file (recommended for local development)**
```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter

# Create .env file (this file is already in .gitignore - safe!)
cat > .env << 'EOF'
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password-here
SENDER_EMAIL=your-email@gmail.com
SENDER_NAME=Your Name
EOF

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)
```

**Option B: Quick test (temporary - only for current terminal session)**
```bash
export SMTP_PASSWORD="your-16-char-app-password-here"
# Remove spaces if any: abcd efgh ijkl mnop → abcdefghijklmnop
```

**Option C: Add to your shell profile (permanent for local)**
```bash
# Add to ~/.zshrc (since you're using zsh)
echo 'export SMTP_PASSWORD="your-16-char-app-password-here"' >> ~/.zshrc
source ~/.zshrc
```

**Option D: For Cloud/CI/CD (GitHub Actions, Docker, etc.)**
- Use GitHub Secrets: Settings → Secrets and variables → Actions
- Use Docker secrets or environment variables
- Use your cloud platform's secrets management (AWS Secrets Manager, etc.)
- **Never** hardcode passwords in code or config files!

## Step 4: Verify config.json

Make sure `config.json` has `smtp_password: null` (not your actual password):

```json
"outreach": {
    "enabled": true,
    "smtp_provider": "gmail",
    "smtp_user": "your-email@gmail.com",
    "smtp_password": null,  // ← Must be null! Use SMTP_PASSWORD env var instead
    "sender_email": "your-email@gmail.com",
    "sender_name": "Your Name"
}
```

## Step 5: Test SMTP Connection

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
python3 Project/run_outreach.py --test-smtp
```

Expected output:
```
✅ SMTP connection test successful!
```

If you see an error:
- ❌ **"SMTP Authentication failed"** → Check that you're using the App Password (16 chars), not your regular password
- ❌ **"SMTP credentials are missing"** → Make sure you exported the environment variable
- ❌ **"Connection timeout"** → Check your internet connection

## Step 6: Verify Environment Variable is Set

```bash
# Check if it's set
echo $SMTP_PASSWORD

# Should show your password (or nothing if not set)
```

## Troubleshooting

### "App passwords" option not showing?
- Make sure 2-Factor Authentication is enabled first
- Try: Google Account → Security → 2-Step Verification → scroll down to "App passwords"

### Still getting authentication errors?
1. Double-check the password has no spaces
2. Make sure you're using the App Password, not your regular Gmail password
3. Try generating a new App Password
4. Verify the email in config.json matches your Gmail account

### Password format
- Gmail App Passwords are 16 characters
- They may be shown with spaces: `abcd efgh ijkl mnop`
- Remove spaces when using: `abcdefghijklmnop`

