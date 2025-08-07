from flask_migrate import Migrate
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import time
from sqlalchemy.exc import OperationalError
import os

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://product_service:productpassword@postgres/product_db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://product_service:productpassword@localhost/product_db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app)

app.app_context().push()

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500), nullable=True)

@app.route("/products", methods=["GET"])
def get_products():
    products = Product.query.all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description
        } for p in products
    ])


@app.route("/products", methods=["POST"])
def create_product():
    data = request.get_json()

    name = data.get("name")
    price = data.get("price")
    description = data.get("description")

    if not name or price is None:
        return jsonify({'error': 'Name and price are required'}), 400

    try:
        product = Product(name=name, price=float(price), description=description)
        db.session.add(product)
        db.session.commit()
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
    db.session.delete(product)
    db.session.commit()
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
        # db.create_all()
    app.run(host='0.0.0.0', port=5002, debug=True)
