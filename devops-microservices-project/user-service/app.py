from flask_migrate import Migrate
from flask import Flask, jsonify, request
import os
import requests
import redis
from model import db, User, Product
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import time
from sqlalchemy.exc import OperationalError
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mysecretkey')
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user_service:userpassword@localhost/user_db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
CORS(app)

app.app_context().push()

redis_host = os.environ.get('REDIS_HOST', 'redis')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

@app.route('/user/<int:user_id>')
def get_user(user_id):

    cache_key = f"user:{user_id}"
    cached_user = redis_client.get(cache_key)
    
    if cached_user:
        return jsonify({"user": json.loads(cached_user), "cached": True})
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    products_count = Product.query.filter_by(user_id=user_id).count()

    user_data = {
        "id": user.id,
        "name": user.name,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "products_created": products_count
    }

    # Cache for 120 seconds
    redis_client.setex(cache_key, 120, json.dumps(user_data))
    return jsonify({"user": user_data, "cached": False})


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("password"):
        return jsonify({"error": "Name and password are required"}), 400

    if User.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(data["password"])
    user = User(name=data["name"], password=hashed_password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(name=data.get("name")).first()

    if not user or not check_password_hash(user.password, data.get("password")):
        return jsonify({"error": "Invalid credentials"}), 401

    # update user last login
    user.last_login = datetime.datetime.utcnow()
    db.session.commit()

    token = jwt.encode({
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }, app.config["SECRET_KEY"], algorithm="HS256")

    return jsonify({"token": token})

@app.route("/health")
def health():
    return "OK", 200

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
