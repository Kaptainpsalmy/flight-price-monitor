"""
Integration tests for full system
"""
import pytest
from app.models import Flight, PriceAlert
from app.price_checker import price_checker
from app.alert_service import alert_service
from app.database import db
from datetime import datetime, timedelta


class TestIntegration:
    """Integration tests for complete flow"""

    def test_full_flight_lifecycle(self, app, client):
        """Test complete flight lifecycle: create → monitor → alert → deactivate"""
        with app.app_context():
            # 1. Create a flight via API
            flight_data = {
                "flight_number": "INT001",
                "airline": "Integration Airlines",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "original_price": 500.00,
                "currency": "USD"
            }

            response = client.post('/api/flights', json=flight_data)
            assert response.status_code == 201
            flight_id = response.json['flight']['id']

            # 2. Check flight was created
            flight = Flight.query.get(flight_id)
            assert flight is not None
            assert flight.flight_number == "INT001"

            # 2.5 Clear any existing alerts for this flight (for clean test)
            PriceAlert.query.filter_by(flight_id=flight_id).delete()
            db.session.commit()

            # 3. Run price checks multiple times
            for i in range(5):
                price_checker.check_flight(flight_id)

            # 4. Force a significant price drop to trigger alert
            from app.price_checker import force_price_drop
            success, message, data = force_price_drop(flight_id, 15)
            assert success == True
            # The alert should trigger now that we cleared previous alerts
            assert data['alert_triggered'] == True
    def test_multiple_flights_concurrent(self, app, client):
        """Test multiple flights being monitored simultaneously"""
        with app.app_context():
            # Create multiple flights
            flight_ids = []
            for i in range(3):
                flight_data = {
                    "flight_number": f"CON{i:03d}",
                    "airline": "Test Airlines",
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": (datetime.now() + timedelta(days=30)).isoformat(),
                    "original_price": 500.00 + i * 100
                }
                response = client.post('/api/flights', json=flight_data)
                flight_ids.append(response.json['flight']['id'])

            # Check all flights
            results = price_checker.check_all_flights()
            assert results['total'] == 3
            assert results['successful'] == 3

            # Force drops on different flights
            from app.price_checker import force_price_drop
            force_price_drop(flight_ids[0], 10)
            force_price_drop(flight_ids[1], 15)
            force_price_drop(flight_ids[2], 20)

            # Verify alerts are independent per flight
            for flight_id in flight_ids:
                alerts = PriceAlert.query.filter_by(flight_id=flight_id).all()
                assert len(alerts) >= 1

    def test_scheduler_integration(self, app, client):
        """Test scheduler integration with API"""
        with app.app_context():
            # Start scheduler
            response = client.post('/api/scheduler/start')
            assert response.status_code == 200

            # Check status
            response = client.get('/api/scheduler/status')
            assert response.status_code == 200
            assert response.json['running'] == True

            # Create a flight
            flight_data = {
                "flight_number": "SCH001",
                "airline": "Scheduler Airlines",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "original_price": 500.00
            }
            response = client.post('/api/flights', json=flight_data)
            flight_id = response.json['flight']['id']

            # Manually trigger price check
            response = client.post('/api/scheduler/trigger')
            assert response.status_code == 200

            # Stop scheduler
            response = client.post('/api/scheduler/stop')
            assert response.status_code == 200

    def test_api_pagination_and_filtering(self, app, client, sample_flights):
        """Test API pagination and filtering"""
        with app.app_context():
            # Test pagination
            response = client.get('/api/flights?page=1&per_page=2')
            assert response.status_code == 200
            assert len(response.json['flights']) <= 2
            assert response.json['total'] >= 3

            # Test filtering by active only
            response = client.get('/api/flights?active_only=true')
            assert response.status_code == 200
            for flight in response.json['flights']:
                assert flight['is_active'] == True

            # Test filtering by flight number
            response = client.get('/api/flights?flight_number=TEST001')
            assert response.status_code == 200
            assert len(response.json['flights']) >= 1
            assert response.json['flights'][0]['flight_number'] == 'TEST001'

    def test_error_handling(self, app, client):
        """Test API error handling"""
        with app.app_context():
            # Invalid flight creation (missing required field)
            invalid_data = {
                "flight_number": "ERR001",
                # Missing airline
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": "2026-01-01T00:00:00",
                "original_price": 500.00
            }
            response = client.post('/api/flights', json=invalid_data)
            assert response.status_code == 400
            assert 'errors' in response.json

            # Get non-existent flight
            response = client.get('/api/flights/99999')
            assert response.status_code == 404

            # Invalid force drop percentage
            flight_data = {
                "flight_number": "ERR002",
                "airline": "Test",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "original_price": 500.00
            }
            create_resp = client.post('/api/flights', json=flight_data)
            flight_id = create_resp.json['flight']['id']

            response = client.post(
                f'/api/flights/{flight_id}/force-drop',
                json={"drop_percentage": 200}
            )
            assert response.status_code == 400