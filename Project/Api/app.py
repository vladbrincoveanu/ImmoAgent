#!/usr/bin/env python3
"""
home.ai - Modern Property Search Interface
A beautiful web UI for browsing and filtering Vienna real estate listings
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson import ObjectId
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import math
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from Integration.minio_handler import MinIOHandler
from Application.scoring import score_apartment_simple as score_apartment

# Load configuration
def load_config():
    """Load configuration from config.json"""
    try:
        # Look for config in multiple locations
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'config.json'),  # Project/config.json
            os.path.join(os.path.dirname(__file__), '..', 'Application', 'config.json'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'),
            os.path.join(os.path.dirname(__file__), 'config.json')
        ]
        
        for config_path in possible_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        
        print("No config.json found in any of the expected locations")
        return {}
    except Exception as e:
        print(f"Could not load config.json: {e}")
        return {}

config = load_config()

# Set up Flask app with new UI folder paths
app = Flask(__name__, template_folder='../UI/templates', static_folder='../UI/static')

# Production configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'"
    return response

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# User model for authentication
class User(UserMixin):
    def __init__(self, user_id, username, email, role='user'):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role

# MongoDB connection from config
MONGO_URI = config.get('mongodb_uri', 'mongodb://localhost:27017/')
DB_NAME = 'immo'
COLLECTION_NAME = 'listings'
USERS_COLLECTION = 'users'

class PropertyDatabase:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]
        self.users_collection = self.db[USERS_COLLECTION]
        
        # Initialize admin user if not exists
        self._init_admin_user()
    
    def _init_admin_user(self):
        """Initialize admin user if not exists"""
        admin_user = self.users_collection.find_one({'username': 'admin'})
        if not admin_user:
            # Create default admin user only if ADMIN_PASSWORD is set
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                print("⚠️  No ADMIN_PASSWORD environment variable set. Skipping admin user creation.")
                print("💡 Set ADMIN_PASSWORD environment variable to create default admin user.")
                return
            
            admin_user = {
                'username': 'admin',
                'email': 'admin@home.ai',
                'password_hash': generate_password_hash(admin_password),
                'role': 'admin',
                'created_at': datetime.utcnow(),
                'last_login': None
            }
            self.users_collection.insert_one(admin_user)
            print("✅ Admin user created with username: admin")
            print("🔐 Password: [Set via ADMIN_PASSWORD environment variable]")
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user and return User object if valid"""
        user_doc = self.users_collection.find_one({'username': username})
        if user_doc and check_password_hash(user_doc['password_hash'], password):
            # Update last login
            self.users_collection.update_one(
                {'_id': user_doc['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            return User(
                user_id=str(user_doc['_id']),
                username=user_doc['username'],
                email=user_doc['email'],
                role=user_doc.get('role', 'user')
            )
        return None
    
    def create_user(self, username: str, email: str, password: str, role: str = 'user') -> bool:
        """Create a new user"""
        # Check if user already exists
        if self.users_collection.find_one({'$or': [{'username': username}, {'email': email}]}):
            return False
        
        user_doc = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'role': role,
            'created_at': datetime.utcnow(),
            'last_login': None
        }
        result = self.users_collection.insert_one(user_doc)
        return result.inserted_id is not None
    
    def get_properties(self, filters: Dict = None, sort_by: str = 'processed_at', sort_order: int = -1, 
                      page: int = 1, per_page: int = 12) -> Dict:
        """Get properties with filtering, sorting, and pagination"""
        try:
            # Build query
            query = {}
            initial_sum = None
            monthly_cost_min = None
            monthly_cost_max = None
            if filters:
                # Extract and remove special filters
                if 'initial_sum' in filters:
                    initial_sum = filters.pop('initial_sum', None)
                if 'monthly_cost_min' in filters:
                    monthly_cost_min = filters.pop('monthly_cost_min', None)
                if 'monthly_cost_max' in filters:
                    monthly_cost_max = filters.pop('monthly_cost_max', None)
                # Build the rest of the query as before
                if filters.get('price_min'):
                    query['price_total'] = {'$gte': int(filters['price_min'])}
                if filters.get('price_max'):
                    if 'price_total' in query:
                        query['price_total']['$lte'] = int(filters['price_max'])
                    else:
                        query['price_total'] = {'$lte': int(filters['price_max'])}
                if filters.get('area_min'):
                    query['area_m2'] = {'$gte': float(filters['area_min'])}
                if filters.get('area_max'):
                    if 'area_m2' in query:
                        query['area_m2']['$lte'] = float(filters['area_max'])
                    else:
                        query['area_m2'] = {'$lte': float(filters['area_max'])}
                if filters.get('rooms_min'):
                    query['rooms'] = {'$gte': int(filters['rooms_min'])}
                if filters.get('rooms_max'):
                    if 'rooms' in query:
                        query['rooms']['$lte'] = int(filters['rooms_max'])
                    else:
                        query['rooms'] = {'$lte': int(filters['rooms_max'])}
                if filters.get('bezirk'):
                    query['bezirk'] = filters['bezirk']
                if filters.get('year_min'):
                    query['year_built'] = {'$gte': int(filters['year_min'])}
                if filters.get('year_max'):
                    if 'year_built' in query:
                        query['year_built']['$lte'] = int(filters['year_max'])
                    else:
                        query['year_built'] = {'$lte': int(filters['year_max'])}
                if filters.get('energy_class'):
                    query['energy_class'] = filters['energy_class']
                if filters.get('condition'):
                    query['condition'] = {'$regex': filters['condition'], '$options': 'i'}
                if filters.get('source'):
                    query['source'] = filters['source']
                if filters.get('price_per_m2_min') or filters.get('price_per_m2_max'):
                    price_per_m2_query = {}
                    if filters.get('price_per_m2_min'):
                        price_per_m2_query['$gte'] = float(filters['price_per_m2_min'])
                    if filters.get('price_per_m2_max'):
                        price_per_m2_query['$lte'] = float(filters['price_per_m2_max'])
                    query['price_per_m2'] = price_per_m2_query
                if filters.get('unbefristet_vermietet'):
                    query['unbefristet_vermietet'] = True
                # Add total_monthly_cost query if needed
                if monthly_cost_min is not None or monthly_cost_max is not None:
                    monthly_cost_query = {}
                    if monthly_cost_min is not None:
                        monthly_cost_query['$gte'] = float(monthly_cost_min)
                    if monthly_cost_max is not None:
                        monthly_cost_query['$lte'] = float(monthly_cost_max)
                    query['total_monthly_cost'] = monthly_cost_query
            # Pagination
            skip = (page - 1) * per_page
            print(f"[DEBUG] Query: {query}, Page: {page}, Skip: {skip}, Per Page: {per_page}")
            
            # Validate sort_by
            valid_sort_fields = ['score', 'processed_at', 'price_total', 'price_per_m2', 'area_m2', 'hwb_value', 'total_monthly_cost']
            if sort_by not in valid_sort_fields:
                sort_by = 'processed_at'  # Default to processed_at instead of score
            # If sorting by score, fetch all documents, calculate scores, sort, then paginate
            if sort_by == 'score':
                total = self.collection.count_documents(query)
                # Fetch all documents that match the query
                cursor = self.collection.find(query)
                properties = []
                for doc in cursor:
                    score = score_apartment(doc)
                    doc['score'] = score
                    if initial_sum is not None and doc.get('price_total'):
                        price_total = doc['price_total']
                        loan_amount = price_total - initial_sum
                        annual_rate = 3.5
                        years = 25
                        monthly_rate = annual_rate / 12 / 100
                        num_payments = years * 12
                        if monthly_rate == 0:
                            base_payment = loan_amount / num_payments
                        else:
                            base_payment = loan_amount * (
                                monthly_rate * (1 + monthly_rate) ** num_payments
                            ) / ((1 + monthly_rate) ** num_payments - 1)
                        doc['calculated_monatsrate'] = round(base_payment, 2)
                        doc['mortgage_details'] = {
                            'loan_amount': loan_amount,
                            'annual_rate': annual_rate,
                            'years': years
                        }
                        betriebskosten = doc.get('betriebskosten', 0)
                        doc['total_monthly_cost'] = round(base_payment + (betriebskosten or 0), 2)
                    else:
                        doc['calculated_monatsrate'] = None
                        doc['mortgage_details'] = None
                        doc['total_monthly_cost'] = doc.get('total_monthly_cost', 0)
                    doc['_id'] = str(doc['_id'])
                    properties.append(doc)
                
                # Sort by score
                properties.sort(key=lambda x: x['score'], reverse=(sort_order == -1))
                
                # Apply pagination after sorting
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paginated_properties = properties[start_idx:end_idx]
                
                return {
                    'properties': paginated_properties,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': math.ceil(total / per_page)
                }
            # Otherwise, sort by the requested field (including total_monthly_cost)
            skip = (page - 1) * per_page
            total = self.collection.count_documents(query)
            cursor = self.collection.find(query).sort(sort_by, sort_order).skip(skip).limit(per_page)
            properties = []
            for doc in cursor:
                score = score_apartment(doc)
                doc['score'] = score
                if initial_sum is not None and doc.get('price_total'):
                    price_total = doc['price_total']
                    loan_amount = price_total - initial_sum
                    annual_rate = 3.5
                    years = 25
                    monthly_rate = annual_rate / 12 / 100
                    num_payments = years * 12
                    if monthly_rate == 0:
                        base_payment = loan_amount / num_payments
                    else:
                        base_payment = loan_amount * (
                            monthly_rate * (1 + monthly_rate) ** num_payments
                        ) / ((1 + monthly_rate) ** num_payments - 1)
                    doc['calculated_monatsrate'] = round(base_payment, 2)
                    doc['mortgage_details'] = {
                        'loan_amount': loan_amount,
                        'annual_rate': annual_rate,
                        'years': years
                    }
                    betriebskosten = doc.get('betriebskosten', 0)
                    doc['total_monthly_cost'] = round(base_payment + (betriebskosten or 0), 2)
                else:
                    doc['calculated_monatsrate'] = None
                    doc['mortgage_details'] = None
                    doc['total_monthly_cost'] = doc.get('total_monthly_cost', 0)
                doc['_id'] = str(doc['_id'])
                properties.append(doc)
            return {
                'properties': properties,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': math.ceil(total / per_page)
            }
            
        except Exception as e:
            print(f"Database error: {e}")
            return {'properties': [], 'total': 0, 'page': 1, 'per_page': per_page, 'pages': 0}
    
    def get_districts(self) -> List[str]:
        """Get unique districts"""
        try:
            districts = self.collection.distinct('bezirk')
            return sorted([d for d in districts if d])
        except Exception as e:
            print(f"Error getting districts: {e}")
            return []
    
    def get_sources(self) -> List[str]:
        """Get unique sources"""
        try:
            sources = self.collection.distinct('source')
            return sorted([s for s in sources if s])
        except Exception as e:
            print(f"Error getting sources: {e}")
            return []
    
    def get_property_by_id(self, property_id: str) -> Optional[Dict]:
        """Get a single property by ID"""
        try:
            doc = self.collection.find_one({'_id': ObjectId(property_id)})
            if doc:
                # Calculate score
                score = score_apartment(doc)
                doc['score'] = score
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            print(f"Error getting property: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            total_properties = self.collection.count_documents({})
            avg_price = self.collection.aggregate([
                {'$match': {'price_total': {'$exists': True, '$ne': None}}},
                {'$group': {'_id': None, 'avg': {'$avg': '$price_total'}}}
            ]).next().get('avg', 0)
            
            avg_area = self.collection.aggregate([
                {'$match': {'area_m2': {'$exists': True, '$ne': None}}},
                {'$group': {'_id': None, 'avg': {'$avg': '$area_m2'}}}
            ]).next().get('avg', 0)
            
            # Get source breakdown
            source_stats = list(self.collection.aggregate([
                {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]))
            
            return {
                'total_properties': total_properties,
                'avg_price': round(avg_price, 0) if avg_price else 0,
                'avg_area': round(avg_area, 1) if avg_area else 0,
                'source_breakdown': source_stats
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {'total_properties': 0, 'avg_price': 0, 'avg_area': 0, 'source_breakdown': []}

# Initialize database
db = PropertyDatabase()

@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    user_doc = db.users_collection.find_one({'_id': ObjectId(user_id)})
    if user_doc:
        return User(
            user_id=str(user_doc['_id']),
            username=user_doc['username'],
            email=user_doc['email'],
            role=user_doc.get('role', 'user')
        )
    return None

# Custom template filters
@app.template_filter('datetime')
def datetime_filter(timestamp):
    """Convert timestamp to readable datetime"""
    if timestamp:
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
        except:
            return str(timestamp)
    return 'N/A'

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        user = db.authenticate_user(username, password)
        if user:
            login_user(user, remember=True)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page)
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all fields.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
        
        # Create user
        if db.create_user(username, email, password):
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists.', 'error')
    
    return render_template('register.html')

@app.route('/')
@login_required
def index():
    """Main page with property listings"""
    # Get filter parameters
    filters = {
        'price_min': request.args.get('price_min'),
        'price_max': request.args.get('price_max'),
        'area_min': request.args.get('area_min'),
        'area_max': request.args.get('area_max'),
        'rooms_min': request.args.get('rooms_min'),
        'rooms_max': request.args.get('rooms_max'),
        'bezirk': request.args.get('bezirk'),
        'year_min': request.args.get('year_min'),
        'year_max': request.args.get('year_max'),
        'energy_class': request.args.get('energy_class'),
        'condition': request.args.get('condition'),
        'source': request.args.get('source'),
        'price_per_m2_min': request.args.get('price_per_m2_min'),
        'price_per_m2_max': request.args.get('price_per_m2_max'),
        'unbefristet_vermietet': request.args.get('unbefristet_vermietet') == '1',
        'monthly_cost_min': request.args.get('monthly_cost_min'),
        'monthly_cost_max': request.args.get('monthly_cost_max'),
        'initial_sum': request.args.get('initial_sum') # Add initial_sum to filters
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None and v != ''}
    
    # Remove empty or unset filters for monthly cost and initial sum, and ensure they are valid numbers
    for key in ['monthly_cost_min', 'monthly_cost_max', 'initial_sum']:
        if key in filters:
            try:
                if filters[key] is None or filters[key] == '' or str(filters[key]).strip() == '':
                    filters.pop(key)
                else:
                    # Try to convert to float, if fails, remove
                    filters[key] = float(filters[key])
            except Exception:
                filters.pop(key)

    # Get sort parameters
    sort_by = request.args.get('sort', 'score')  # Default to score
    sort_order = -1 if request.args.get('order', 'desc') == 'desc' else 1
    page = int(request.args.get('page', 1))
    
    # Get properties
    result = db.get_properties(filters, sort_by, sort_order, page)
    
    # Get additional data
    districts = db.get_districts()
    sources = db.get_sources()
    stats = db.get_stats()
    
    return render_template('index.html',
                         properties=result['properties'],
                         total=result['total'],
                         page=result['page'],
                         pages=result['pages'],
                         filters=filters,
                         districts=districts,
                         sources=sources,
                         stats=stats,
                         sort_by=sort_by,
                         sort_order=sort_order)

@app.route('/property/<property_id>')
@login_required
def property_detail(property_id):
    """Property detail page"""
    property_data = db.get_property_by_id(property_id)
    if not property_data:
        return "Property not found", 404
    
    return render_template('property_detail.html', property=property_data)

@app.route('/api/properties')
@login_required
def api_properties():
    """API endpoint for properties"""
    filters = request.args.to_dict()
    result = db.get_properties(filters)
    return jsonify(result)

@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for statistics"""
    stats = db.get_stats()
    return jsonify(stats)

@app.route('/images/<path:image_path>')
def serve_image(image_path):
    """Serve images from MinIO"""
    try:
        minio_handler = MinIOHandler()
        
        # Get presigned URL for the image
        image_url = minio_handler.get_image_url(image_path)
        
        if image_url:
            # Redirect to the presigned URL
            return redirect(image_url)
        else:
            # Return 404 if image not found
            return "Image not found", 404
            
    except Exception as e:
        print(f"Error serving image {image_path}: {e}")
        return "Error serving image", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 