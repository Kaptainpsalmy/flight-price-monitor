"""
Database connection setup
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)

    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        print("Database tables created/verified")