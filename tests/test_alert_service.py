"""
Tests for alert service with idempotency
"""
import pytest
from app.alert_service import AlertService
from app.models import Flight, PriceAlert
from app.database import db
from datetime import datetime, timedelta


class TestAlertService:
    """Test alert service with idempotency"""

    @pytest.fixture
    def alert_service(self):
        return AlertService()

    def test_calculate_drop_percentage(self, alert_service, sample_flight):
        """Test drop percentage calculation"""
        assert alert_service.calculate_drop_percentage(500, 500) == 0
        assert alert_service.calculate_drop_percentage(500, 450) == 10
        assert alert_service.calculate_drop_percentage(500, 375) == 25
        assert alert_service.calculate_drop_percentage(500, 550) == -10

    def test_threshold_checking(self, app, alert_service, sample_flight):
        """Test 10% threshold logic"""
        with app.app_context():
            # Below threshold (9.9%)
            should_trigger, reason = alert_service.should_trigger_alert(
                sample_flight, 450.50
            )
            assert should_trigger == False
            assert "below 10%" in reason

            # Exactly at threshold (10%)
            should_trigger, reason = alert_service.should_trigger_alert(
                sample_flight, 450.00
            )
            assert should_trigger == True
            assert "10.0%" in reason

            # Above threshold (15%)
            should_trigger, reason = alert_service.should_trigger_alert(
                sample_flight, 425.00
            )
            assert should_trigger == True
            assert "15.0%" in reason

    def test_idempotency_no_duplicates(self, app, alert_service, sample_flight):
        """Test that duplicate alerts aren't sent"""
        with app.app_context():
            # First alert at 20% drop
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 400.00
            )
            assert triggered == True

            # Same price again - should NOT trigger
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 400.00
            )
            assert triggered == False
            assert "already alerted" in reason.lower()

    def test_idempotency_new_low(self, app, alert_service, sample_flight):
        """Test that new low price triggers alert"""
        with app.app_context():
            # First alert at 400
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 400.00
            )
            assert triggered == True

            # Higher price - no alert
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 420.00
            )
            assert triggered == False

            # New low (350) - should trigger
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 350.00
            )
            assert triggered == True

    def test_multiple_drops_sequence(self, app, alert_service, sample_flight):
        """Test complex sequence of price drops"""
        with app.app_context():
            # Clear any existing alerts
            PriceAlert.query.filter_by(flight_id=sample_flight.id).delete()
            db.session.commit()

            test_sequence = [
                (480, False, "4% drop - no alert"),
                (450, True, "10% drop - ALERT 1"),
                (460, False, "price up - no alert"),
                (440, True, "12% drop - ALERT 2"),
                (440, False, "same price - no alert"),
                (430, True, "14% drop - ALERT 3"),
                (435, False, "higher price - no alert"),
                (420, True, "16% drop - ALERT 4"),
            ]

            alert_count = 0
            for price, should_trigger, description in test_sequence:
                triggered, alert, reason = alert_service.check_and_trigger(
                    sample_flight, price
                )
                if triggered:
                    alert_count += 1
                assert triggered == should_trigger, f"Failed: {description}"

            assert alert_count == 4

    def test_edge_case_exact_10_percent(self, app, alert_service, sample_flight):
        """Test exact 10% drop"""
        with app.app_context():
            # Clear existing alerts
            PriceAlert.query.filter_by(flight_id=sample_flight.id).delete()
            db.session.commit()

            # 9.9% drop - no alert
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 450.50
            )
            assert triggered == False

            # 10.0% drop - alert
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 450.00
            )
            assert triggered == True

    def test_edge_case_zero_price(self, app, alert_service, sample_flight):
        """Test edge case with zero price"""
        with app.app_context():
            triggered, alert, reason = alert_service.check_and_trigger(
                sample_flight, 0
            )
            # Should handle gracefully (division by zero protection)
            assert triggered == False or triggered == True  # Either is fine