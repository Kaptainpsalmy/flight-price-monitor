"""
Test email notifications directly
Run with: python test_email.py
"""
from app import create_app
from app.database import db
from app.models import Flight
from app.alert_service import alert_service
from datetime import datetime, timedelta


def test_email():
    app = create_app()
    with app.app_context():
        # Create a test flight
        flight = Flight(
            flight_number="EMAILTEST",
            airline="Test Airlines",
            origin="JFK",
            destination="LAX",
            departure_date=datetime.now() + timedelta(days=30),
            original_price=500.00,
            current_price=500.00,
            is_active=True
        )
        db.session.add(flight)
        db.session.commit()

        print("1️⃣ Created test flight")

        # Clear any existing alerts
        from app.models import PriceAlert
        PriceAlert.query.filter_by(flight_id=flight.id).delete()
        db.session.commit()

        print("2️⃣ Cleared existing alerts")

        # Trigger alert with 15% drop
        print("3️⃣ Triggering 15% drop alert...")
        triggered, alert, reason = alert_service.check_and_trigger(flight, 425.00)

        if triggered:
            print("✅ Alert triggered successfully!")
            print(f"   Reason: {reason}")
            print(f"   Alert ID: {alert.id if alert else 'N/A'}")

            # Check if email was sent (check logs)
            print("\n📧 Check the server logs for: '📧 Email alert sent to...'")
        else:
            print(f"❌ Alert not triggered: {reason}")


if __name__ == "__main__":
    test_email()