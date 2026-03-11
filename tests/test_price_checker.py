"""
Tests for price checker logic
"""
import pytest
from app.price_checker import PriceChecker, MockPriceGenerator
from app.models import Flight, PriceHistory
from app.database import db
from datetime import datetime, timedelta

class TestMockPriceGenerator:
    """Test mock price generation"""

    def test_generate_price_normal(self, app, sample_flight):
        """Test normal price generation"""
        with app.app_context():
            generator = MockPriceGenerator(sample_flight)
            price = generator.generate_price()

            assert isinstance(price, float)
            assert price > 0
            # Should be within reasonable range
            assert price >= sample_flight.original_price * 0.5
            assert price <= sample_flight.original_price * 1.5

    def test_price_pattern_selection(self, app, sample_flight):
        """Test pattern selection based on days until departure"""
        with app.app_context():
            # Last minute (less than 3 days)
            sample_flight.departure_date = datetime.now() + timedelta(days=2)
            generator = MockPriceGenerator(sample_flight)
            assert generator.get_pattern() == 'last_minute'

            # Sale (3-7 days)
            sample_flight.departure_date = datetime.now() + timedelta(days=5)
            generator = MockPriceGenerator(sample_flight)
            assert generator.get_pattern() == 'sale'

            # Normal (7-60 days)
            sample_flight.departure_date = datetime.now() + timedelta(days=30)
            generator = MockPriceGenerator(sample_flight)
            assert generator.get_pattern() == 'normal'

            # Holiday (>60 days)
            sample_flight.departure_date = datetime.now() + timedelta(days=61)
            generator = MockPriceGenerator(sample_flight)
            assert generator.get_pattern() == 'holiday'

class TestPriceChecker:
    """Test price checker service"""

    def test_check_flight_success(self, app, sample_flight):
        """Test successful price check"""
        with app.app_context():
            checker = PriceChecker()
            success, message, data = checker.check_flight(sample_flight.id)

            assert success == True
            assert data is not None
            assert 'old_price' in data
            assert 'new_price' in data
            assert 'drop_percentage' in data

    def test_check_nonexistent_flight(self, app):
        """Test checking non-existent flight"""
        with app.app_context():
            checker = PriceChecker()
            success, message, data = checker.check_flight(99999)

            assert success == False
            assert "not found" in message.lower()
            assert data is None

    def test_check_inactive_flight(self, app, sample_flight):
        """Test checking inactive flight"""
        with app.app_context():
            sample_flight.is_active = False
            db.session.commit()

            checker = PriceChecker()
            success, message, data = checker.check_flight(sample_flight.id)

            assert success == False
            assert "inactive" in message.lower()
            assert data is None

    def test_check_departed_flight(self, app, sample_flight):
        """Test checking departed flight"""
        with app.app_context():
            sample_flight.departure_date = datetime.now() - timedelta(days=1)
            db.session.commit()

            checker = PriceChecker()
            success, message, data = checker.check_flight(sample_flight.id)

            assert success == False
            assert "departed" in message.lower()

            # Flight should be deactivated
            flight = Flight.query.get(sample_flight.id)
            assert flight.is_active == False

    def test_price_history_created(self, app, sample_flight):
        """Test that price history is created"""
        with app.app_context():
            checker = PriceChecker()
            checker.check_flight(sample_flight.id)

            # Check history was created
            history = PriceHistory.query.filter_by(flight_id=sample_flight.id).first()
            assert history is not None
            assert history.price is not None
            assert history.checked_at is not None

    def test_check_all_flights(self, app, sample_flights):
        """Test checking all flights"""
        with app.app_context():
            checker = PriceChecker()
            results = checker.check_all_flights()

            assert results['total'] == len(sample_flights)
            assert results['successful'] == len(sample_flights)
            assert results['failed'] == 0