from flask_migrate import Migrate
from flask import Flask, jsonify, request
from flask_cors import CORS
import time
from model import db, Product
import redis
from sqlalchemy.exc import OperationalError
import os
import json

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://product_service:productpassword@localhost/product_db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
CORS(app)

app.app_context().push()

redis_host = os.environ.get('REDIS_HOST', 'redis')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

@app.route('/product/<int:product_id>')
def get_product(product_id):
    cache_key = f"product:{product_id}"
    cached_product = redis_client.get(cache_key)
    if cached_product:
        return jsonify({"product": json.loads(cached_product), "cached": True})

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    product_data = {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "description": product.description
    }
    # Cache for 120 seconds
    redis_client.setex(cache_key, 120, json.dumps(product_data))
    return jsonify({"product": product_data, "cached": False})

@app.route("/products", methods=["GET"])
def get_products():
    cache_key = "products:all"
    cached_products = redis_client.get(cache_key)
    if cached_products:
        return jsonify(json.loads(cached_products))

    products = Product.query.all()
    products_list = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description
        } for p in products
    ]
    redis_client.setex(cache_key, 60, json.dumps(products_list))
    return jsonify(products_list)

@app.route("/products/count")
def count_products():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id required"}), 400

    cache_key = f"products:count:user:{user_id}"
    cached_count = redis_client.get(cache_key)
    if cached_count is not None:
        return jsonify({"count": int(cached_count), "cached": True})

    count = Product.query.filter_by(user_id=user_id).count()
    redis_client.setex(cache_key, 30, count)
    return jsonify({"count": count, "cached": False})

@app.route("/products", methods=["POST"])
def create_product():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")
    description = data.get("description")
    user_id = data.get("user_id")

    if not name or price is None or user_id is None:
        return jsonify({'error': 'Name, price, and user_id are required'}), 400

    try:
        product = Product(name=name, price=float(price), description=description, user_id=user_id)
        db.session.add(product)
        db.session.commit()
        # Invalidate related caches
        redis_client.delete("products:all")
        redis_client.delete(f"products:count:user:{user_id}")
        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    product.name = data.get("name", product.name)
    product.price = data.get("price", product.price)
    product.description = data.get("description", product.description)

    try:
        db.session.commit()
        # Invalidate caches
        redis_client.delete(f"product:{product_id}")
        redis_client.delete("products:all")
        redis_client.delete(f"products:count:user:{product.user_id}")
        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    user_id = product.user_id
    db.session.delete(product)
    db.session.commit()
    # Invalidate caches
    redis_client.delete(f"product:{product_id}")
    redis_client.delete("products:all")
    redis_client.delete(f"products:count:user:{user_id}")
    return jsonify({"message": "Product deleted"})

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
    app.run(host='0.0.0.0', port=5002, debug=True)
