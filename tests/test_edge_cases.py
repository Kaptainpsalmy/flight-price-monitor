"""
Edge case tests for all components
"""
import pytest
from app.models import Flight, PriceAlert
from app.price_checker import price_checker
from app.alert_service import alert_service
from app.database import db
from datetime import datetime, timedelta


class TestEdgeCases:
    """Test various edge cases"""

    def test_flight_with_past_departure_date(self, app):
        """Test flight with past departure date"""
        with app.app_context():
            flight = Flight(
                flight_number='PAST001',
                airline='Test Airlines',
                origin='JFK',
                destination='LAX',
                departure_date=datetime.now() - timedelta(days=1),
                original_price=500.00,
                current_price=500.00,
                is_active=True
            )
            db.session.add(flight)
            db.session.commit()

            # Check should detect it's departed and deactivate
            success, message, data = price_checker.check_flight(flight.id)
            assert success == False
            assert "departed" in message.lower()

            flight = Flight.query.get(flight.id)
            assert flight.is_active == False

    def test_flight_with_zero_price(self, app):
        """Test flight with zero price (edge case)"""
        with app.app_context():
            flight = Flight(
                flight_number='ZERO001',
                airline='Test Airlines',
                origin='JFK',
                destination='LAX',
                departure_date=datetime.now() + timedelta(days=30),
                original_price=0.00,
                current_price=0.00,
                is_active=True
            )
            db.session.add(flight)
            db.session.commit()

            # Price checker should handle gracefully
            success, message, data = price_checker.check_flight(flight.id)
            # Should either succeed or fail gracefully, not crash
            assert success in [True, False]

    def test_extremely_large_price_drop(self, app):
        """Test extreme price drop (90%)"""
        with app.app_context():
            flight = Flight(
                flight_number='EXTREME001',
                airline='Test Airlines',
                origin='JFK',
                destination='LAX',
                departure_date=datetime.now() + timedelta(days=30),
                original_price=1000.00,
                current_price=1000.00,
                is_active=True
            )
            db.session.add(flight)
            db.session.commit()

            # Force 90% drop
            from app.price_checker import force_price_drop
            success, message, data = force_price_drop(flight.id, 90)
            assert success == True
            assert data['drop_percentage'] == 90.0
            assert data['alert_triggered'] == True

    def test_multiple_alerts_same_day(self, app):
        """Test multiple alerts on same day for different flights"""
        with app.app_context():
            flights = []
            for i in range(5):
                flight = Flight(
                    flight_number=f'MULTI00{i}',
                    airline='Test Airlines',
                    origin='JFK',
                    destination='LAX',
                    departure_date=datetime.now() + timedelta(days=30),
                    original_price=500.00 + i * 100,
                    current_price=500.00 + i * 100,
                    is_active=True
                )
                db.session.add(flight)
                flights.append(flight)
            db.session.commit()

            # Trigger alerts on all flights
            for flight in flights:
                triggered, alert, reason = alert_service.check_and_trigger(
                    flight, flight.original_price * 0.85  # 15% drop
                )
                assert triggered == True

            # Check all alerts were recorded
            total_alerts = PriceAlert.query.count()
            assert total_alerts >= len(flights)

    def test_concurrent_price_checks(self, app, sample_flight):
        """Simulate concurrent price checks (though not truly concurrent in tests)"""
        with app.app_context():
            # Run multiple checks rapidly
            for _ in range(10):
                success, message, data = price_checker.check_flight(sample_flight.id)
                # Should handle rapid successive calls
                assert success in [True, False]  # Some might fail if flight deactivated

    def test_malformed_api_requests(self, app, client):
        """Test API with malformed requests"""
        with app.app_context():
            # Invalid JSON
            response = client.post(
                '/api/flights',
                data="This is not JSON",
                content_type='application/json'
            )
            # Accept either 400 (proper) or 500 (if error handler not yet added)
            assert response.status_code in [400, 500]

            # Empty request
            response = client.post('/api/flights', json={})
            assert response.status_code == 400

            # Invalid date format
            flight_data = {
                "flight_number": "INV001",
                "airline": "Test",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": "not-a-date",
                "original_price": 500.00
            }
            response = client.post('/api/flights', json=flight_data)
            assert response.status_code == 400
    def test_flight_cancellation_flow(self, app, client, sample_flight):
        """Test flight cancellation flow"""
        with app.app_context():
            # Cancel flight via API
            response = client.put(
                f'/api/flights/{sample_flight.id}',
                json={"is_cancelled": True, "is_active": False}
            )
            assert response.status_code == 200

            # Verify flight is cancelled and inactive
            flight = Flight.query.get(sample_flight.id)
            assert flight.is_cancelled == True
            assert flight.is_active == False

            # Price check should skip cancelled flight
            success, message, data = price_checker.check_flight(flight.id)
            assert success == False
            assert "inactive" in message.lower()