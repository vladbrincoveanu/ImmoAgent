#!/usr/bin/env python3
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the Flask app
from Api.app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 