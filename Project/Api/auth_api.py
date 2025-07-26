#!/usr/bin/env python3
"""
Secure Authentication API for GitHub Pages UI
Connects to MongoDB Atlas for user management
"""

import os
import jwt
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for GitHub Pages

# Configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-super-secret-key-change-this-in-production')
JWT_EXPIRATION_HOURS = 24

# MongoDB Atlas connection
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
DB_NAME = 'immo_auth'
USERS_COLLECTION = 'users'

# Initialize MongoDB client
try:
    client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
    db = client[DB_NAME]
    users_collection = db[USERS_COLLECTION]
    logger.info("✅ Connected to MongoDB Atlas for authentication")
except Exception as e:
    logger.error(f"❌ Failed to connect to MongoDB: {e}")
    raise

def create_jwt_token(user_id: str, username: str) -> str:
    """Create JWT token for user"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_jwt_token(token: str) -> Optional[Dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return None

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_default_user():
    """Create default user if none exists"""
    try:
        # Check if any users exist
        if users_collection.count_documents({}) == 0:
            # Get admin password from environment variable
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                logger.warning("⚠️  No ADMIN_PASSWORD environment variable set. Skipping default user creation.")
                logger.info("💡 Set ADMIN_PASSWORD environment variable to create default admin user.")
                return False
            
            # Create default admin user
            default_user = {
                'username': 'admin',
                'password_hash': hash_password(admin_password),
                'email': 'admin@immoscouter.com',
                'role': 'admin',
                'created_at': datetime.utcnow(),
                'last_login': None
            }
            
            users_collection.insert_one(default_user)
            logger.info("✅ Created default admin user")
            logger.info("🔐 Default credentials:")
            logger.info("   Username: admin")
            logger.info("   Password: [Set via ADMIN_PASSWORD environment variable]")
            logger.info("⚠️  Please change these credentials after first login!")
            
            return True
    except Exception as e:
        logger.error(f"❌ Error creating default user: {e}")
        return False

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Find user in database
        user = users_collection.find_one({'username': username})
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        
        # Create JWT token
        token = create_jwt_token(str(user['_id']), user['username'])
        
        return jsonify({
            'token': token,
            'user': {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user.get('email'),
                'role': user.get('role', 'user')
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/validate', methods=['GET'])
@require_auth
def validate_token():
    """Validate JWT token"""
    try:
        user_id = request.user['user_id']
        username = request.user['username']
        
        # Get user from database
        user = users_collection.find_one({'_id': user_id})
        if not user:
            return jsonify({'error': 'User not found'}), 401
        
        return jsonify({
            'user': {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user.get('email'),
                'role': user.get('role', 'user')
            }
        })
        
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Check if user already exists
        if users_collection.find_one({'username': username}):
            return jsonify({'error': 'Username already exists'}), 409
        
        # Create new user
        new_user = {
            'username': username,
            'password_hash': hash_password(password),
            'email': email,
            'role': 'user',
            'created_at': datetime.utcnow(),
            'last_login': None
        }
        
        result = users_collection.insert_one(new_user)
        
        return jsonify({
            'message': 'User created successfully',
            'user_id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/properties', methods=['GET'])
@require_auth
def get_properties():
    """Get properties from MongoDB (requires authentication)"""
    try:
        # Connect to the main immo database
        immo_db = client['immo']
        listings_collection = immo_db['listings']
        
        # Get properties with pagination
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Get properties sorted by score
        properties = list(listings_collection.find(
            {},
            {'_id': 0}  # Exclude MongoDB _id
        ).sort('score', -1).skip(offset).limit(limit))
        
        return jsonify(properties)
        
    except Exception as e:
        logger.error(f"Error fetching properties: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    # Create default user on startup
    create_default_user()
    
    # Run the app
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False) 