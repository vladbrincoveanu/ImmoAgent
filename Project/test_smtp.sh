#!/bin/bash
# Quick SMTP connection test script

echo "🔌 Testing SMTP Connection for Immo-Scouter"
echo "============================================"
echo ""

# Check if SMTP_PASSWORD is set
if [ -z "$SMTP_PASSWORD" ]; then
    echo "❌ SMTP_PASSWORD environment variable is not set!"
    echo ""
    echo "📝 To set it, run:"
    echo "   export SMTP_PASSWORD='your-gmail-app-password'"
    echo ""
    echo "💡 Don't have an App Password yet?"
    echo "   1. Go to: https://myaccount.google.com/apppasswords"
    echo "   2. Generate one for 'Mail'"
    echo "   3. Copy the 16-character password"
    echo ""
    exit 1
fi

# Check if SMTP_USER is set (optional, will use config.json if not)
if [ -z "$SMTP_USER" ]; then
    echo "ℹ️  SMTP_USER not set, will use value from config.json"
fi

echo "✅ Environment variables found"
echo "   SMTP_USER: ${SMTP_USER:-'from config.json'}"
echo "   SMTP_PASSWORD: ${SMTP_PASSWORD:0:4}**** (hidden)"
echo ""
echo "🧪 Testing connection..."
echo ""

# Run the test
python3 Project/run_outreach.py --test-smtp

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ SMTP connection test passed!"
    echo "🎉 You're ready to send outreach emails!"
else
    echo ""
    echo "❌ SMTP connection test failed"
    echo ""
    echo "💡 Common issues:"
    echo "   - Make sure you're using a Gmail App Password (not your regular password)"
    echo "   - App Passwords are 16 characters (remove spaces if any)"
    echo "   - Verify 2FA is enabled on your Google account"
    echo "   - Check that the email in config.json matches your Gmail account"
fi

exit $exit_code




