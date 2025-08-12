from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    password = Column(String(200), nullable=False)
    last_login = Column(DateTime, nullable=True)
    products = relationship('Product', backref='user', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Float, nullable=True)
    description = Column(String(500), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)