import pytest
from app import create_app
from app.database import db
from app.models import Flight, PriceAlert, PriceHistory
from datetime import datetime, timedelta
import tempfile
import os


@pytest.fixture
def app():
    """Create application for testing"""
    # test config
    os.environ['FLASK_ENV'] = 'testing'

    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['PRICE_CHECK_INTERVAL_MINUTES'] = 0.1  # Very fast for testing

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def sample_flight(app):
    """Create a sample flight for testing"""
    with app.app_context():
        flight = Flight(
            flight_number='TEST001',
            airline='Test Airlines',
            origin='JFK',
            destination='LAX',
            departure_date=datetime.now() + timedelta(days=30),
            original_price=500.00,
            current_price=500.00,
            is_active=True
        )
        db.session.add(flight)
        db.session.commit()

        yield flight

        db.session.delete(flight)
        db.session.commit()


@pytest.fixture
def sample_flights(app):
    """Create multiple sample flights for testing"""
    with app.app_context():
        flights = [
            Flight(
                flight_number=f'TEST00{i}',
                airline='Test Airlines',
                origin='JFK',
                destination='LAX',
                departure_date=datetime.now() + timedelta(days=30 * i),
                original_price=500.00,
                current_price=500.00,
                is_active=True
            ) for i in range(1, 4)
        ]

        for flight in flights:
            db.session.add(flight)
        db.session.commit()

        yield flights

        for flight in flights:
            db.session.delete(flight)
        db.session.commit()


@pytest.fixture
def sample_alert(app, sample_flight):
    """Create a sample alert for testing"""
    with app.app_context():
        alert = PriceAlert(
            flight_id=sample_flight.id,
            alert_price=450.00,
            original_price=500.00,
            drop_percentage=10.0,
            alert_sent=True
        )
        db.session.add(alert)
        db.session.commit()

        yield alert

        db.session.delete(alert)
        db.session.commit()