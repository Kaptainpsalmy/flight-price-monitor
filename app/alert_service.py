from .database import db
from .models import Flight, PriceAlert
from .logger import setup_logger
from datetime import datetime, timezone
import traceback
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


logger = setup_logger('alert_service')

class AlertService:
    """Service for managing price drop alerts with idempotency and email notifications"""

    def __init__(self):
        self.logger = logger
        # Email configuration
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_username = os.environ.get('SMTP_USERNAME', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.from_email = os.environ.get('FROM_EMAIL', '')
        self.to_email = os.environ.get('ALERT_EMAIL', '')
        self.email_enabled = all([self.smtp_username, self.smtp_password, self.from_email, self.to_email])

        if self.email_enabled:
            self.logger.info("Email notifications enabled")
        else:
            self.logger.warning("Email notifications disabled - missing configuration")

    def calculate_drop_percentage(self, original_price, current_price):
        if original_price == 0:
            return 0
        drop = ((original_price - current_price) / original_price) * 100
        return round(drop, 2)

    def should_trigger_alert(self, flight, current_price):
        try:
            # Calculate current drop percentage
            drop_percentage = self.calculate_drop_percentage(flight.original_price, current_price)

            # Is drop >= 10%?
            if drop_percentage < 10:
                return False, f"Drop {drop_percentage}% is below 10% threshold"

            # Has flight already departed?
            if flight.days_until_departure < 0:
                return False, "Flight has already departed"

            # Is flight still active?
            if not flight.is_active:
                return False, "Flight is inactive"

            # IDEMPOTENCY CHECK
            last_alert = PriceAlert.query.filter_by(
                flight_id=flight.id
            ).order_by(PriceAlert.triggered_at.desc()).first()

            if last_alert:
                if current_price >= last_alert.alert_price:
                    return False, f"Already alerted at ${last_alert.alert_price} (current: ${current_price})"

                # check if there is an alert recently the type
                time_since_last_alert = (datetime.now(timezone.utc) - last_alert.triggered_at.replace(tzinfo=timezone.utc)).total_seconds()
                if time_since_last_alert < 3600:  # 1 hour cooldown
                    drop_difference = abs(drop_percentage - last_alert.drop_percentage)
                    if drop_difference < 2:  # Within 2% of last alert
                        return False, f"Similar drop ({drop_difference:.1f}% diff) within cooldown period"

            # check all alerts if we have not alert for the same price only alerts if the price drops to new
            all_alerts = PriceAlert.query.filter_by(flight_id=flight.id).all()
            if all_alerts:
                # check for lowest price we have entered for
                lowest_alerted_price = min(alert.alert_price for alert in all_alerts)
                if current_price >= lowest_alerted_price:
                    return False, f"Already alerted for lower price: ${lowest_alerted_price}"

            # All checks passed - should trigger alert
            return True, f"Price dropped {drop_percentage}% to ${current_price}"

        except Exception as e:
            self.logger.error(f"Error in should_trigger_alert: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False, f"Error checking alert: {str(e)}"

    def trigger_alert(self, flight, current_price, drop_percentage):

        try:
            self.logger.info(f"🔔 TRIGGERING ALERT for {flight.flight_number}")

            # Create alert record in database
            alert = PriceAlert(
                flight_id=flight.id,
                alert_price=current_price,
                original_price=flight.original_price,
                drop_percentage=drop_percentage,
                alert_sent=True,
                notification_method='multiple',  # Will track both console and email
                triggered_at=datetime.now(timezone.utc)
            )

            db.session.add(alert)
            db.session.commit()

            self.send_console_alert(flight, current_price, drop_percentage)

            if self.email_enabled:
                self.send_email_alert(flight, current_price, drop_percentage)

            # Log to file
            self.logger.info(f"Alert triggered: {flight.flight_number} dropped {drop_percentage}% to ${current_price}")

            return alert

        except Exception as e:
            self.logger.error(f"Error triggering alert: {str(e)}")
            db.session.rollback()
            return None

    def send_console_alert(self, flight, current_price, drop_percentage):
        alert_message = self.format_alert_message(flight, current_price, drop_percentage)

        print("\n" + "="*60)
        print("🔔 PRICE DROP ALERT!")
        print("="*60)
        print(alert_message)
        print("="*60 + "\n")

    def send_email_alert(self, flight, current_price, drop_percentage):
        try:
            subject = f"✈️ Flight Price Drop Alert: {flight.flight_number}"

            # HTML email body
            html_body = self.format_email_html(flight, current_price, drop_percentage)

            text_body = self.format_email_text(flight, current_price, drop_percentage)

            #  message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = self.to_email

            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Secure the connection
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            self.logger.info(f"📧 Email alert sent to {self.to_email}")

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {str(e)}")
            self.logger.error(traceback.format_exc())

    def format_email_text(self, flight, current_price, drop_percentage):
        return f"""
FLIGHT PRICE DROP ALERT ✈️

Flight: {flight.flight_number}
Airline: {flight.airline}
Route: {flight.origin} → {flight.destination}
Departure: {flight.departure_date.strftime('%Y-%m-%d %H:%M')}
Days until departure: {flight.days_until_departure}

PRICE UPDATE:
Original Price: ${flight.original_price}
Current Price: ${current_price}
Drop: {drop_percentage}%

⚡ This is a {drop_percentage}% price drop - below the 10% threshold!

Book now before the price increases again!

---
Price Monitor Service
"""

    def format_email_html(self, flight, current_price, drop_percentage):
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 10px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .flight-details {{
            background-color: #f9f9f9;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .price {{
            font-size: 24px;
            color: #4CAF50;
            font-weight: bold;
        }}
        .old-price {{
            text-decoration: line-through;
            color: #999;
        }}
        .drop {{
            font-size: 20px;
            color: #f44336;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ Flight Price Drop Alert!</h1>
        </div>
        
        <div class="flight-details">
            <h2>{flight.flight_number} - {flight.airline}</h2>
            <p><strong>Route:</strong> {flight.origin} → {flight.destination}</p>
            <p><strong>Departure:</strong> {flight.departure_date.strftime('%Y-%m-%d %H:%M')}</p>
            <p><strong>Days until departure:</strong> {flight.days_until_departure}</p>
        </div>
        
        <div style="text-align: center; padding: 20px;">
            <h3>Price Update</h3>
            <p>
                <span class="old-price">${flight.original_price}</span>
                → 
                <span class="price">${current_price}</span>
            </p>
            <p class="drop">⬇️ {drop_percentage}% Drop!</p>
            <p style="font-size: 18px;">⚡ Below the 10% threshold!</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <p style="font-size: 18px;"><strong>Book now before the price increases again!</strong></p>
        </div>
        
        <div class="footer">
            <p>This is an automated alert from your Price Monitor Service</p>
            <p>© 2026 Price Monitor - All rights reserved</p>
        </div>
    </div>
</body>
</html>
"""

    def format_alert_message(self, flight, current_price, drop_percentage):
        """Format a nice console alert message"""
        return f"""
✈️ Flight: {flight.flight_number} ({flight.airline})
📍 Route: {flight.origin} → {flight.destination}
📅 Departure: {flight.departure_date.strftime('%Y-%m-%d %H:%M')}
⏱️ Days until departure: {flight.days_until_departure}

💰 Price Update:
   Original: ${flight.original_price}
   Current:  ${current_price}
   Drop:     {drop_percentage}%

⚡ This is a {drop_percentage}% price drop - below the 10% threshold!
        """

    def check_and_trigger(self, flight, current_price):
        try:
            self.logger.debug(f"Checking alert for flight {flight.flight_number} at ${current_price}")

            # Calculate drop percentage
            drop_percentage = self.calculate_drop_percentage(flight.original_price, current_price)

            # Check if we should trigger
            should_trigger, reason = self.should_trigger_alert(flight, current_price)

            if should_trigger:
                # Trigger the alert
                alert = self.trigger_alert(flight, current_price, drop_percentage)
                return True, alert, reason
            else:
                self.logger.debug(f"No alert: {reason}")
                return False, None, reason

        except Exception as e:
            self.logger.error(f"Error in check_and_trigger: {str(e)}")
            return False, None, f"Error: {str(e)}"


# Create singleton instance
alert_service = AlertService()

# Convenience function for the price checker to call
def check_and_trigger_alerts(flight, current_price):
    triggered, alert, reason = alert_service.check_and_trigger(flight, current_price)
    return triggered