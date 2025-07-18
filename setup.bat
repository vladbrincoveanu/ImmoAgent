@echo off
REM 🏠 Immo-Scouter Setup Script for Windows
REM This script helps you set up the immo-scouter system quickly

echo 🏠 Welcome to Immo-Scouter Setup!
echo ==================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is required but not installed.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

echo ✅ Python found: 
python --version

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📚 Installing dependencies...
pip install -r Project\requirements.txt
echo ✅ Dependencies installed

REM Check if config.json exists
if not exist "config.json" (
    echo ⚙️  Setting up configuration...
    if exist "config.json.default" (
        copy config.json.default config.json
        echo ✅ Configuration file created from template
        echo ⚠️  Please edit config.json with your settings:
        echo    - MongoDB connection string
        echo    - Telegram bot tokens and chat IDs
        echo    - OpenAI API key (optional)
    ) else (
        echo ❌ config.json.default not found
        pause
        exit /b 1
    )
) else (
    echo ✅ Configuration file already exists
)

REM Check if MongoDB is running
echo 🗄️  Checking MongoDB connection...
docker ps | findstr mongo >nul 2>&1
if not errorlevel 1 (
    echo ✅ MongoDB running in Docker
) else (
    echo ⚠️  MongoDB not detected
    echo    Please ensure MongoDB is running:
    echo    - Docker: docker-compose up -d
    echo    - Local: mongod
)

REM Create log directory
if not exist "log" (
    echo 📝 Creating log directory...
    mkdir log
    echo ✅ Log directory created
)

echo.
echo 🎉 Setup complete!
echo ==================
echo.
echo Next steps:
echo 1. Edit config.json with your settings
echo 2. Start MongoDB (if not running)
echo 3. Run the system:
echo    set PYTHONPATH=Project
echo    python Project\Application\main.py
echo.
echo For more information, see README.md
echo.
echo Happy house hunting! 🏠✨
pause 