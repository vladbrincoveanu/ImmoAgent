#!/bin/bash

# 🏠 Immo-Scouter Setup Script
# This script helps you set up the immo-scouter system quickly

set -e

echo "🏠 Welcome to Immo-Scouter Setup!"
echo "=================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r Project/requirements.txt
echo "✅ Dependencies installed"

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "⚙️  Setting up configuration..."
    if [ -f "config.json.default" ]; then
        cp config.json.default config.json
        echo "✅ Configuration file created from template"
        echo "⚠️  Please edit config.json with your settings:"
        echo "   - MongoDB connection string"
        echo "   - Telegram bot tokens and chat IDs"
        echo "   - OpenAI API key (optional)"
    else
        echo "❌ config.json.default not found"
        exit 1
    fi
else
    echo "✅ Configuration file already exists"
fi

# Check if MongoDB is running
echo "🗄️  Checking MongoDB connection..."
if command -v docker &> /dev/null && docker ps | grep -q mongo; then
    echo "✅ MongoDB running in Docker"
elif command -v mongod &> /dev/null; then
    echo "✅ MongoDB found locally"
else
    echo "⚠️  MongoDB not detected"
    echo "   Please ensure MongoDB is running:"
    echo "   - Docker: docker-compose up -d"
    echo "   - Local: mongod"
fi

# Create log directory
if [ ! -d "log" ]; then
    echo "📝 Creating log directory..."
    mkdir -p log
    echo "✅ Log directory created"
fi

echo ""
echo "🎉 Setup complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Edit config.json with your settings"
echo "2. Start MongoDB (if not running)"
echo "3. Run the system:"
echo "   PYTHONPATH=Project python Project/Application/main.py"
echo ""
echo "For more information, see README.md"
echo ""
echo "Happy house hunting! 🏠✨" 