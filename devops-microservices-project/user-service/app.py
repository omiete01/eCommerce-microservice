from flask_migrate import Migrate
from flask import Flask, jsonify, request
import os
import requests
import redis
from model import db, User
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import logging
import datetime
import time
from sqlalchemy.exc import OperationalError
import json
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mysecretkey')
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
REQUEST_COUNT = Counter('user_service_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('user_service_request_duration_seconds', 'Request duration')
ACTIVE_USERS = Gauge('user_service_active_users', 'Number of active users')
LOGIN_ATTEMPTS = Counter('user_service_login_attempts_total', 'Login attempts', ['status'])

# Structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': 'user_service',
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'user_name'):
            log_entry['user_name'] = record.user_name
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
            
        return json.dumps(log_entry)

# Set up logging
logger = logging.getLogger('user_service')
logger.setLevel(logging.INFO)

# Remove any existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create console handler with JSON formatter
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

logger.info("User service started", extra={'endpoint': 'startup'})

@app.route('/user/<int:user_id>')
def get_user(user_id):
    start_time = time.time()
    logger.info(f"Get user request for user_id: {user_id}", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id})
    
    try:
        cache_key = f"user:{user_id}"
        cached_user = redis_client.get(cache_key)

        if cached_user:
            logger.info("User found in cache", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'cached': True})
            user_data = json.loads(cached_user)
            try:
                resp = requests.get(f'http://product_service:5002/products/count?user_id={user_id}', timeout=2)
                if resp.status_code == 200:
                    user_data["products_created"] = resp.json().get("count", 0)
            except Exception as e:
                logger.warning("Failed to fetch product count", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'error': str(e)})
                user_data["products_created"] = "unavailable"
            
            REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '200').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            logger.info("User retrieved from cache", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'status_code': 200})
            return jsonify({"user": user_data, "cached": True})

        user = User.query.get(user_id)
        if not user:
            logger.warning("User not found", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'status_code': 404})
            REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '404').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "User not found"}), 404
        
        try:
            resp = requests.get(f'http://product_service:5002/products/count?user_id={user_id}', timeout=2)
            if resp.status_code == 200:
                products_count = resp.json().get("count", 0)
            else:
                products_count = "unavailable"
        except Exception as e:
            logger.warning("Failed to fetch product count from product service", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'error': str(e)})
            products_count = "unavailable"

        user_data = {
            "user_id": user.id,
            "name": user.name,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "products_created": products_count
        }

        redis_client.setex(cache_key, 120, json.dumps(user_data))
        REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("User retrieved from database", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'status_code': 200})
        return jsonify({"user": user_data, "cached": False})
    except Exception as e:
        logger.error("Error retrieving user", extra={'endpoint': '/user/<int:user_id>', 'user_id': user_id, 'error': str(e)})
        REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/register", methods=["POST"])
def register():
    start_time = time.time()
    try:
        data = request.get_json()
        logger.info("Registration attempt", extra={'endpoint': '/register', 'user_name': data.get('name') if data else None})
        
        if not data or not data.get("name") or not data.get("password"):
            logger.warning("Registration failed - missing name or password", extra={'endpoint': '/register', 'status_code': 400})
            REQUEST_COUNT.labels('POST', '/register', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "Name and password are required"}), 400

        if User.query.filter_by(name=data["name"]).first():
            logger.warning("Registration failed - user already exists", extra={'endpoint': '/register', 'user_name': data["name"], 'status_code': 400})
            REQUEST_COUNT.labels('POST', '/register', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "User already exists"}), 400

        hashed_password = generate_password_hash(data["password"])
        user = User(name=data["name"], password=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        ACTIVE_USERS.inc()
        REQUEST_COUNT.labels('POST', '/register', '201').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("User registered successfully", extra={'endpoint': '/register', 'user_name': data["name"], 'user_id': user.id, 'status_code': 201})
        return jsonify({"message": "User created"}), 201
    except Exception as e:
        logger.error("Registration error", extra={'endpoint': '/register', 'error': str(e)})
        REQUEST_COUNT.labels('POST', '/register', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    start_time = time.time()
    try:
        data = request.get_json()
        logger.info("Login attempt", extra={'endpoint': '/login', 'user_name': data.get('name') if data else None})
        
        user = User.query.filter_by(name=data.get("name")).first()

        if not user or not check_password_hash(user.password, data.get("password")):
            LOGIN_ATTEMPTS.labels('failed').inc()
            REQUEST_COUNT.labels('POST', '/login', '401').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            logger.warning("Invalid login credentials", extra={'endpoint': '/login', 'user_name': data.get('name'), 'status_code': 401})
            return jsonify({"error": "Invalid credentials"}), 401

        user.last_login = datetime.datetime.utcnow()
        db.session.commit()
        
        LOGIN_ATTEMPTS.labels('success').inc()
        ACTIVE_USERS.inc()

        payload = {
            "user_id": user.id,
            "userId": user.id,
            "name": user.name,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        
        try:
            token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode('utf-8')
        except Exception as e:
            logger.error("Token generation failed", extra={'endpoint': '/login', 'user_id': user.id, 'error': str(e)})
            REQUEST_COUNT.labels('POST', '/login', '500').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": f"Token generation failed: {str(e)}"}), 500

        REQUEST_COUNT.labels('POST', '/login', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        logger.info("Successful login", extra={'endpoint': '/login', 'user_id': user.id, 'user_name': user.name, 'status_code': 200})
        return jsonify({"token": token})
    except Exception as e:
        logger.error("Login error", extra={'endpoint': '/login', 'error': str(e)})
        LOGIN_ATTEMPTS.labels('failed').inc()
        REQUEST_COUNT.labels('POST', '/login', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

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
    logger.info("Starting user service", extra={'port': 5001})
    app.run(host='0.0.0.0', port=5001, debug=True)