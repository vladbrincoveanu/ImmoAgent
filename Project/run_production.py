#!/usr/bin/env python3
"""
Production server for home.ai
"""

import os
import sys
import logging
from waitress import serve

# Add the Project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for production
os.environ['FLASK_ENV'] = 'production'

# Import the app
from Api.app import app
from production import ProductionConfig

def main():
    """Run the production server"""
    
    # Configure the app for production
    app.config.from_object(ProductionConfig)
    ProductionConfig.init_app(app)
    
    # Get configuration
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5001)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler('/var/log/home-ai/production.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting home.ai production server on {host}:{port}")
    
    try:
        # Run with Waitress (production WSGI server)
        serve(app, host=host, port=port, threads=4)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 