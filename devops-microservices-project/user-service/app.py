from flask_migrate import Migrate
from flask import Flask, jsonify, request
import os
import requests
import redis
from model import db, User
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import time
from sqlalchemy.exc import OperationalError
import json
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

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

@app.route('/user/<int:user_id>')
def get_user(user_id):
    start_time = time.time()
    try:
        cache_key = f"user:{user_id}"
        cached_user = redis_client.get(cache_key)

        if cached_user:
            user_data = json.loads(cached_user)
            try:
                resp = requests.get(f'http://product_service:5002/products/count?user_id={user_id}', timeout=2)
                if resp.status_code == 200:
                    user_data["products_created"] = resp.json().get("count", 0)
            except Exception:
                user_data["products_created"] = "unavailable"
            
            REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '200').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"user": user_data, "cached": True})

        user = User.query.get(user_id)
        if not user:
            REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '404').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "User not found"}), 404
        
        try:
            resp = requests.get(f'http://product_service:5002/products/count?user_id={user_id}', timeout=2)
            if resp.status_code == 200:
                products_count = resp.json().get("count", 0)
            else:
                products_count = "unavailable"
        except Exception:
            products_count = "unavailable"

        user_data = {
            "id": user.id,
            "name": user.name,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "products_created": products_count
        }

        redis_client.setex(cache_key, 120, json.dumps(user_data))
        REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"user": user_data, "cached": False})
    except Exception as e:
        REQUEST_COUNT.labels('GET', '/user/<int:user_id>', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/register", methods=["POST"])
def register():
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or not data.get("name") or not data.get("password"):
            REQUEST_COUNT.labels('POST', '/register', '400').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "Name and password are required"}), 400

        if User.query.filter_by(name=data["name"]).first():
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
        return jsonify({"message": "User created"}), 201
    except Exception as e:
        REQUEST_COUNT.labels('POST', '/register', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    start_time = time.time()
    try:
        data = request.get_json()
        user = User.query.filter_by(name=data.get("name")).first()

        if not user or not check_password_hash(user.password, data.get("password")):
            LOGIN_ATTEMPTS.labels('failed').inc()
            REQUEST_COUNT.labels('POST', '/login', '401').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": "Invalid credentials"}), 401

        user.last_login = datetime.datetime.utcnow()
        db.session.commit()
        
        LOGIN_ATTEMPTS.labels('success').inc()
        ACTIVE_USERS.inc()

        payload = {
            "user_id": user.id,
            "id": user.id,
            "userId": user.id,
            "name": user.name,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        
        try:
            token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode('utf-8')
        except Exception as e:
            REQUEST_COUNT.labels('POST', '/login', '500').inc()
            REQUEST_DURATION.observe(time.time() - start_time)
            return jsonify({"error": f"Token generation failed: {str(e)}"}), 500

        REQUEST_COUNT.labels('POST', '/login', '200').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"token": token})
    except Exception as e:
        LOGIN_ATTEMPTS.labels('failed').inc()
        REQUEST_COUNT.labels('POST', '/login', '500').inc()
        REQUEST_DURATION.observe(time.time() - start_time)
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return "OK", 200

# Prometheus metrics endpoint
@app.route('/metrics')
def metrics():
    resp = generate_latest()
    return resp, 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    with app.app_context():
        for _ in range(10):
            try:
                db.create_all()
                break
            except OperationalError:
                print("Database unavailable, retrying in 2 seconds...")
                time.sleep(2)
    app.run(host='0.0.0.0', port=5001, debug=True)