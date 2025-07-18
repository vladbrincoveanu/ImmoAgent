#!/usr/bin/env python3
"""
home.ai - Modern Property Search Interface
A beautiful web UI for browsing and filtering Vienna real estate listings
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from pymongo import MongoClient
from bson import ObjectId
import json
import os
from datetime import datetime
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
app.secret_key = 'home_ai_secret_key_2024'

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

# MongoDB connection from config
MONGO_URI = config.get('mongodb_uri', 'mongodb://localhost:27017/')
DB_NAME = 'immo'
COLLECTION_NAME = 'listings'

class PropertyDatabase:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]
    
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

@app.route('/')
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
def property_detail(property_id):
    """Property detail page"""
    property_data = db.get_property_by_id(property_id)
    if not property_data:
        return "Property not found", 404
    
    return render_template('property_detail.html', property=property_data)

@app.route('/api/properties')
def api_properties():
    """API endpoint for properties"""
    filters = request.args.to_dict()
    result = db.get_properties(filters)
    return jsonify(result)

@app.route('/api/stats')
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