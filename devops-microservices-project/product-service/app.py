from flask_migrate import Migrate
from flask import Flask, jsonify, request
from flask_cors import CORS
import time
from model import db, Product
import redis
from sqlalchemy.exc import OperationalError
import os
import json
import requests
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
CORS(app)

app.app_context().push()

# Redis setup
redis_host = os.environ.get('REDIS_HOST', 'redis')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Prometheus metrics
REQUEST_COUNT = Counter('product_service_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('product_service_request_duration_seconds', 'Request duration')
PRODUCT_COUNT = Counter('product_service_products_total', 'Total products created', ['operation'])

# Structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': 'product_service',
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'product_id'):
            log_entry['product_id'] = record.product_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
            
        return json.dumps(log_entry)

# Set up logging
logger = logging.getLogger('product_service')
logger.setLevel(logging.INFO)

# Remove any existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create console handler with JSON formatter
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

logger.info("Product service started", extra={'endpoint': 'startup'})

# endpoint to get a single product
@app.route('/product/<int:product_id>')
def get_product(product_id):
    start_time = time.time()
    logger.info(f"Get product request for product_id: {product_id}", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id})
    
    try:
        cache_key = f"product:{product_id}"
        cached_product = redis_client.get(cache_key)
        if cached_product:
            logger.info("Product found in cache", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id, 'cached': True})
            REQUEST_COUNT.labels('GET', '/product/<int:product_id>', '200').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            logger.info("Product retrieved from cache", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id, 'status_code': 200})
            return jsonify({"product": json.loads(cached_product), "cached": True})

        product = Product.query.get(product_id)
        if not product:
            logger.warning("Product not found", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id, 'status_code': 404})
            REQUEST_COUNT.labels('GET', '/product/<int:product_id>', '404').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "Product not found"}), 404

        creator_name = None
        try:
            user_response = requests.get(f'http://user_service:5001/user/{product.user_id}', timeout=2)
            if user_response.status_code == 200:
                user_data = user_response.json()
                creator_name = user_data.get('user', {}).get('name')
        except Exception as e:
            logger.warning("Failed to fetch user info", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id, 'user_id': product.user_id, 'error': str(e)})

        product_data = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "user_id": product.user_id,
            "creator": creator_name
        }
        
        redis_client.setex(cache_key, 120, json.dumps(product_data))
        REQUEST_COUNT.labels('GET', '/product/<int:product_id>', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Product retrieved from database", extra={'endpoint': '/product/<int:product_id>', 'product_id': product.id, 'user_id': product.user_id, 'status_code': 200})
        return jsonify({"product": product_data, "cached": False})
    except Exception as e:
        logger.error("Error retrieving product", extra={'endpoint': '/product/<int:product_id>', 'product_id': product_id, 'error': str(e)})
        REQUEST_COUNT.labels('GET', '/product/<int:product_id>', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

# get all products
@app.route("/products", methods=["GET"])
def get_products():
    start_time = time.time()
    logger.info("Get all products request", extra={'endpoint': '/products'})
    
    try:
        cache_key = "products:all"
        cached_products = redis_client.get(cache_key)
        if cached_products:
            logger.info("Products list found in cache", extra={'endpoint': '/products', 'cached': True})
            REQUEST_COUNT.labels('GET', '/products', '200').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            logger.info("Products retrieved from cache", extra={'endpoint': '/products', 'status_code': 200})
            return jsonify(json.loads(cached_products))

        products = Product.query.all()
        logger.info(f"Retrieved {len(products)} products from database", extra={'endpoint': '/products', 'product_count': len(products)})
        
        products_list = []
        
        for p in products:
            creator_name = None
            try:
                user_response = requests.get(f'http://user_service:5001/user/{p.user_id}', timeout=2)
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    creator_name = user_data.get('user', {}).get('name')
            except Exception as e:
                logger.warning("Failed to fetch user info for product", extra={'endpoint': '/products', 'product_id': p.id, 'user_id': p.user_id, 'error': str(e)})
                
            products_list.append({
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "description": p.description,
                "user_id": p.user_id,
                "creator": creator_name
            })
        
        redis_client.setex(cache_key, 60, json.dumps(products_list))
        REQUEST_COUNT.labels('GET', '/products', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Products retrieved successfully", extra={'endpoint': '/products', 'product_count': len(products_list), 'status_code': 200})
        return jsonify(products_list)
    except Exception as e:
        logger.error("Error retrieving products", extra={'endpoint': '/products', 'error': str(e)})
        REQUEST_COUNT.labels('GET', '/products', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/products/count")
def count_products():
    start_time = time.time()
    user_id = request.args.get("user_id", type=int)
    logger.info(f"Get product count request for user_id: {user_id}", extra={'endpoint': '/products/count', 'user_id': user_id})
    
    try:
        if user_id is None:
            logger.warning("Product count request missing user_id", extra={'endpoint': '/products/count', 'status_code': 400})
            REQUEST_COUNT.labels('GET', '/products/count', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "user_id required"}), 400

        cache_key = f"products:count:user:{user_id}"
        cached_count = redis_client.get(cache_key)
        if cached_count is not None:
            logger.info("Product count found in cache", extra={'endpoint': '/products/count', 'user_id': user_id, 'count': int(cached_count), 'cached': True})
            REQUEST_COUNT.labels('GET', '/products/count', '200').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"count": int(cached_count), "cached": True})

        count = Product.query.filter_by(user_id=user_id).count()
        redis_client.setex(cache_key, 30, count)
        REQUEST_COUNT.labels('GET', '/products/count', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Product count retrieved", extra={'endpoint': '/products/count', 'user_id': user_id, 'count': count, 'status_code': 200})
        return jsonify({"count": count, "cached": False})
    except Exception as e:
        logger.error("Error counting products", extra={'endpoint': '/products/count', 'user_id': user_id, 'error': str(e)})
        REQUEST_COUNT.labels('GET', '/products/count', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

# create products
@app.route("/products", methods=["POST"])
def create_product():
    start_time = time.time()
    try:
        data = request.get_json()
        logger.info("Create product request", extra={'endpoint': '/products', 'user_id': data.get('user_id') if data else None, 'product_name': data.get('name') if data else None})
        
        name = data.get("name")
        price = data.get("price")
        description = data.get("description")
        user_id = data.get("user_id")
        try:
            user_id = int(user_id) if user_id is not None else None
        except ValueError:
            logger.warning("Invalid user_id format", extra={'endpoint': '/products', 'user_id': user_id, 'status_code': 400})
            REQUEST_COUNT.labels('POST', '/products', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({'error': 'Invalid user_id'}), 400

        if not name or price is None or user_id is None:
            logger.warning("Missing required fields for product creation", extra={'endpoint': '/products', 'name': name, 'price': price, 'user_id': user_id, 'status_code': 400})
            REQUEST_COUNT.labels('POST', '/products', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({'error': 'Name, price, and user_id are required'}), 400

        product = Product(name=name, price=float(price), description=description, user_id=user_id)
        db.session.add(product)
        db.session.commit()
        
        PRODUCT_COUNT.labels('create').inc()
        
        creator_name = None
        try:
            user_response = requests.get(f'http://user_service:5001/user/{user_id}', timeout=2)
            if user_response.status_code == 200:
                user_data = user_response.json()
                creator_name = user_data.get('user', {}).get('name')
        except Exception as e:
            logger.warning("Failed to fetch user info for new product", extra={'endpoint': '/products', 'user_id': user_id, 'error': str(e)})
        
        redis_client.delete("products:all")
        redis_client.delete(f"products:count:user:{user_id}")
        
        REQUEST_COUNT.labels('POST', '/products', '201').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Product created successfully", extra={'endpoint': '/products', 'product_id': product.id, 'user_id': user_id, 'product_name': product.name, 'status_code': 201})
        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "user_id": product.user_id,
            "creator": creator_name
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error("Error creating product", extra={'endpoint': '/products', 'user_id': data.get('user_id') if data else None, 'error': str(e)})
        REQUEST_COUNT.labels('POST', '/products', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({'error': str(e)}), 500

# update product
@app.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    start_time = time.time()
    logger.info(f"Update product request for product_id: {product_id}", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id})
    
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        logger.info("Updating product", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'user_id': product.user_id})

        product.name = data.get("name", product.name)
        product.price = data.get("price", product.price)
        product.description = data.get("description", product.description)

        db.session.commit()
        PRODUCT_COUNT.labels('update').inc()
        
        creator_name = None
        try:
            user_response = requests.get(f'http://user_service:5001/user/{product.user_id}', timeout=2)
            if user_response.status_code == 200:
                user_data = user_response.json()
                creator_name = user_data.get('user', {}).get('name')
        except Exception as e:
            logger.warning("Failed to fetch user info for updated product", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'user_id': product.user_id, 'error': str(e)})
        
        redis_client.delete(f"product:{product_id}")
        redis_client.delete("products:all")
        redis_client.delete(f"products:count:user:{product.user_id}")
        
        REQUEST_COUNT.labels('PUT', '/products/<int:product_id>', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Product updated successfully", extra={'endpoint': '/products/<int:product_id>', 'product_id': product.id, 'user_id': product.user_id, 'status_code': 200})
        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "user_id": product.user_id,
            "creator": creator_name
        })
    except Exception as e:
        db.session.rollback()
        logger.error("Error updating product", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'error': str(e)})
        REQUEST_COUNT.labels('PUT', '/products/<int:product_id>', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({'error': str(e)}), 500

# delete product
@app.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    start_time = time.time()
    logger.info(f"Delete product request for product_id: {product_id}", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id})
    
    try:
        product = Product.query.get_or_404(product_id)
        user_id = product.user_id
        logger.info("Deleting product", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'user_id': user_id})
        
        db.session.delete(product)
        db.session.commit()
        PRODUCT_COUNT.labels('delete').inc()
        
        redis_client.delete(f"product:{product_id}")
        redis_client.delete("products:all")
        redis_client.delete(f"products:count:user:{user_id}")
        
        REQUEST_COUNT.labels('DELETE', '/products/<int:product_id>', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Product deleted successfully", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'user_id': user_id, 'status_code': 200})
        return jsonify({"message": "Product deleted"})
    except Exception as e:
        db.session.rollback()
        logger.error("Error deleting product", extra={'endpoint': '/products/<int:product_id>', 'product_id': product_id, 'error': str(e)})
        REQUEST_COUNT.labels('DELETE', '/products/<int:product_id>', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({'error': str(e)}), 500

# health check
@app.route("/health")
def health():
    logger.info("Health check", extra={'endpoint': '/health', 'status_code': 200})
    return "OK", 200

# Prometheus metrics endpoint
@app.route('/metrics')
def metrics():
    logger.info("Metrics endpoint accessed", extra={'endpoint': '/metrics'})
    resp = generate_latest()
    return resp, 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    with app.app_context():
        for _ in range(10):
            try:
                db.create_all()
                break
            except OperationalError:
                logger.warning("Database unavailable, retrying in 2 seconds...")
                print("Database unavailable, retrying in 2 seconds...")
                time.sleep(2)
    logger.info("Starting product service", extra={'port': 5002})
    app.run(host='0.0.0.0', port=5002, debug=True)