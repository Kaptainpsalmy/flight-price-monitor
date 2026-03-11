"""
Unit tests for database models
"""
import pytest
from app.models import Flight, PriceAlert, PriceHistory
from app.database import db
from datetime import datetime, timedelta


class TestFlightModel:
    """Test Flight model"""

    def test_create_flight(self, app, sample_flight):
        """Test flight creation"""
        with app.app_context():
            flight = Flight.query.get(sample_flight.id)
            assert flight is not None
            assert flight.flight_number == 'TEST001'
            assert flight.original_price == 500.00
            assert flight.current_price == 500.00
            assert flight.is_active == True

    def test_price_drop_percentage(self, app, sample_flight):
        """Test price drop calculation"""
        with app.app_context():
            flight = Flight.query.get(sample_flight.id)

            # No drop
            flight.current_price = 500.00
            assert flight.price_drop_percentage == 0.0

            # 10% drop
            flight.current_price = 450.00
            assert flight.price_drop_percentage == 10.0

            # 25% drop
            flight.current_price = 375.00
            assert flight.price_drop_percentage == 25.0

            # Price increase (negative drop)
            flight.current_price = 550.00
            assert flight.price_drop_percentage == -10.0

    def test_days_until_departure(self, app, sample_flight):
        """Test days until departure calculation"""
        with app.app_context():
            flight = Flight.query.get(sample_flight.id)

            # Future flight
            flight.departure_date = datetime.now() + timedelta(days=30)
            assert flight.days_until_departure > 0
            assert flight.days_until_departure <= 31  # Allow for time difference

            # Past flight
            flight.departure_date = datetime.now() - timedelta(days=1)
            assert flight.days_until_departure < 0

    def test_flight_relationships(self, app, sample_flight, sample_alert):
        """Test flight relationships with alerts and history"""
        with app.app_context():
            flight = Flight.query.get(sample_flight.id)

            # Add price history
            history = PriceHistory(
                flight_id=flight.id,
                price=450.00,
                drop_percentage=10.0
            )
            db.session.add(history)
            db.session.commit()

            # Test relationships
            assert len(flight.alerts) == 1
            assert flight.alerts[0].id == sample_alert.id
            assert len(flight.price_history) == 1
            assert flight.price_history[0].price == 450.00

    def test_flight_validation(self, app):
        """Test flight field validation"""
        with app.app_context():
            # Flight with missing required fields should fail
            with pytest.raises(Exception):
                flight = Flight()
                db.session.add(flight)
                db.session.commit()

            db.session.rollback()


class TestPriceAlertModel:
    """Test PriceAlert model"""

    def test_create_alert(self, app, sample_alert):
        """Test alert creation"""
        with app.app_context():
            alert = PriceAlert.query.get(sample_alert.id)
            assert alert is not None
            assert alert.alert_price == 450.00
            assert alert.drop_percentage == 10.0
            assert alert.alert_sent == True

    def test_alert_relationship(self, app, sample_alert, sample_flight):
        """Test alert relationship with flight"""
        with app.app_context():
            alert = PriceAlert.query.get(sample_alert.id)
            flight = alert.flight
            assert flight.id == sample_flight.id
            assert flight.flight_number == 'TEST001'

    def test_alert_timestamp(self, app, sample_alert):
        """Test alert timestamp is set automatically"""
        with app.app_context():
            alert = PriceAlert.query.get(sample_alert.id)
            assert alert.triggered_at is not None
            assert isinstance(alert.triggered_at, datetime)


class TestPriceHistoryModel:
    """Test PriceHistory model"""

    def test_create_history(self, app, sample_flight):
        """Test price history creation"""
        with app.app_context():
            history = PriceHistory(
                flight_id=sample_flight.id,
                price=450.00,
                drop_percentage=10.0,
                notes="Test price check"
            )
            db.session.add(history)
            db.session.commit()

            saved = PriceHistory.query.get(history.id)
            assert saved is not None
            assert saved.price == 450.00
            assert saved.drop_percentage == 10.0
            assert saved.notes == "Test price check"
            assert saved.checked_at is not None

    def test_history_relationship(self, app, sample_flight):
        """Test history relationship with flight"""
        with app.app_context():
            history = PriceHistory(
                flight_id=sample_flight.id,
                price=450.00,
                drop_percentage=10.0
            )
            db.session.add(history)
            db.session.commit()

            saved = PriceHistory.query.get(history.id)
            flight = saved.flight
            assert flight.id == sample_flight.id
            assert flight.flight_number == 'TEST001'