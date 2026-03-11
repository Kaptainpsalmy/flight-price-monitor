"""
Core price checking logic with mock price generation
"""
from .database import db
from .models import Flight, PriceHistory
from .alert_service import check_and_trigger_alerts
from .logger import setup_logger
from datetime import datetime, timezone
import random
import traceback

# Setup logger
logger = setup_logger('price_checker')


class MockPriceGenerator:
    """Generates mock prices to simulate real airline API responses"""

    # Common price fluctuation patterns
    PATTERNS = {
        'normal': lambda p, f: p * f,  # Random fluctuation
        'sale': lambda p, f: p * (0.7 + (f * 0.2)),  # Bigger drop possible
        'holiday': lambda p, f: p * (1.1 + (f * 0.3)),  # Price increase
        'last_minute': lambda p, f: p * (0.6 + (f * 0.4)),  # Volatile
    }

    def __init__(self, flight):
        self.flight = flight
        self.days_until = flight.days_until_departure

    def get_pattern(self):
        """Determine price pattern based on days until departure"""
        if self.days_until < 3:
            return 'last_minute'
        elif self.days_until < 7:
            return 'sale'
        elif self.days_until > 60:
            return 'holiday'
        else:
            return 'normal'

    def generate_price(self):
        """Generate a mock current price for the flight"""
        try:
            pattern = self.get_pattern()
            logger.debug(f"Using {pattern} pattern for flight {self.flight.flight_number}")

            # Base fluctuation
            if pattern == 'last_minute':
                # High volatility for last minute
                fluctuation = random.uniform(0.5, 1.3)
            elif pattern == 'sale':
                # Likely to be cheaper
                fluctuation = random.uniform(0.6, 1.1)
            elif pattern == 'holiday':
                # Likely to be expensive
                fluctuation = random.uniform(1.0, 1.4)
            else:
                # Normal random fluctuation
                fluctuation = random.uniform(0.8, 1.2)

            # Apply pattern-specific logic
            pattern_func = self.PATTERNS.get(pattern, self.PATTERNS['normal'])
            mock_price = pattern_func(self.flight.original_price, fluctuation)

            # Ensure price is never negative and round to 2 decimals
            mock_price = max(0.01, round(mock_price, 2))

            logger.debug(f"Generated price: ${mock_price} (fluctuation: {fluctuation:.2f})")
            return mock_price

        except Exception as e:
            logger.error(f"Error generating mock price: {str(e)}")
            # Fallback to original price with small random change
            fallback = self.flight.original_price * random.uniform(0.95, 1.05)
            return round(fallback, 2)


class PriceChecker:
    """Main price checking service"""

    def __init__(self):
        self.logger = logger

    def check_flight(self, flight_id):
        """
        Check price for a specific flight
        Returns: (success: bool, message: str, data: dict)
        """
        try:
            self.logger.info(f"Checking price for flight ID: {flight_id}")

            # Get flight from database
            flight = Flight.query.get(flight_id)
            if not flight:
                error_msg = f"Flight ID {flight_id} not found"
                self.logger.error(error_msg)
                return False, error_msg, None

            # Check if flight is still active
            if not flight.is_active:
                self.logger.info(f"Flight {flight.flight_number} is inactive, skipping")
                return False, "Flight is inactive", None

            # Check if flight has already departed
            if flight.days_until_departure < 0:
                self.logger.info(f"Flight {flight.flight_number} has already departed, deactivating")
                flight.is_active = False
                db.session.commit()
                return False, "Flight has departed", None

            # Generate new price
            generator = MockPriceGenerator(flight)
            new_price = generator.generate_price()

            # Store old price for comparison
            old_price = flight.current_price

            # Update flight price
            flight.current_price = new_price
            flight.last_checked = datetime.now(timezone.utc)

            # Save to price history
            history = PriceHistory(
                flight_id=flight.id,
                price=new_price,
                drop_percentage=flight.price_drop_percentage,
                notes=f"Price changed from ${old_price} to ${new_price}"
            )
            db.session.add(history)

            # Commit the price update
            db.session.commit()

            # Replace line 135 with:
            self.logger.info(f"Flight {flight.flight_number} price updated: ${old_price} -> ${new_price}")
            # Check if alert should be triggered (separate transaction)
            alert_triggered = check_and_trigger_alerts(flight, new_price)

            result_data = {
                'flight_id': flight.id,
                'flight_number': flight.flight_number,
                'old_price': old_price,
                'new_price': new_price,
                'drop_percentage': flight.price_drop_percentage,
                'alert_triggered': alert_triggered
            }

            return True, "Price check completed", result_data

        except Exception as e:
            self.logger.error(f"Error checking flight {flight_id}: {str(e)}")
            self.logger.error(traceback.format_exc())
            db.session.rollback()
            return False, f"Error: {str(e)}", None

    def check_all_flights(self):
        """
        Check prices for all active flights
        Returns: Summary dictionary
        """
        self.logger.info("=" * 50)
        self.logger.info("STARTING PRICE CHECK CYCLE FOR ALL FLIGHTS")
        self.logger.info("=" * 50)

        try:
            # Get all active flights that haven't departed
            flights = Flight.query.filter_by(
                is_active=True,
                is_cancelled=False
            ).all()

            # Filter out departed flights in Python (more precise than SQL for datetime)
            active_flights = [f for f in flights if f.days_until_departure >= 0]

            self.logger.info(f"Found {len(active_flights)} active flights to check")

            results = {
                'total': len(active_flights),
                'successful': 0,
                'failed': 0,
                'alerts_triggered': 0,
                'details': []
            }

            for flight in active_flights:
                success, message, data = self.check_flight(flight.id)

                if success:
                    results['successful'] += 1
                    if data and data.get('alert_triggered'):
                        results['alerts_triggered'] += 1
                    results['details'].append({
                        'flight': flight.flight_number,
                        'status': 'success',
                        'data': data
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'flight': flight.flight_number,
                        'status': 'failed',
                        'message': message
                    })

            # Summary log
            self.logger.info("=" * 50)
            self.logger.info("PRICE CHECK CYCLE COMPLETED")
            self.logger.info(
                f"Total: {results['total']}, Successful: {results['successful']}, Failed: {results['failed']}, Alerts: {results['alerts_triggered']}")
            self.logger.info("=" * 50)

            return results

        except Exception as e:
            self.logger.error(f"Error in check_all_flights: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                'error': str(e),
                'total': 0,
                'successful': 0,
                'failed': 0,
                'alerts_triggered': 0
            }

    def force_price_drop(self, flight_id, drop_percentage):
        """
        Utility function to force a price drop for testing
        This bypasses the mock generator and directly sets a lower price
        """
        try:
            self.logger.info(f"Forcing {drop_percentage}% price drop for flight {flight_id}")

            flight = Flight.query.get(flight_id)
            if not flight:
                return False, "Flight not found", None

            # Calculate new price
            new_price = flight.original_price * (1 - drop_percentage / 100)
            new_price = round(new_price, 2)

            # Update flight
            old_price = flight.current_price
            flight.current_price = new_price
            flight.last_checked = datetime.utcnow()

            # Save to history
            history = PriceHistory(
                flight_id=flight.id,
                price=new_price,
                drop_percentage=flight.price_drop_percentage,
                notes=f"FORCED DROP: {drop_percentage}% (was ${old_price})"
            )
            db.session.add(history)
            db.session.commit()

            # Check for alert
            alert_triggered = check_and_trigger_alerts(flight, new_price)

            result = {
                'flight_id': flight.id,
                'flight_number': flight.flight_number,
                'old_price': old_price,
                'new_price': new_price,
                'drop_percentage': flight.price_drop_percentage,
                'alert_triggered': alert_triggered
            }

            return True, f"Forced {drop_percentage}% drop applied", result

        except Exception as e:
            self.logger.error(f"Error forcing price drop: {str(e)}")
            db.session.rollback()
            return False, str(e), None


# Create singleton instance
price_checker = PriceChecker()


# Convenience functions
def check_all_prices():
    """Wrapper function for scheduler to call"""
    return price_checker.check_all_flights()


def check_single_price(flight_id):
    """Wrapper function for manual checks"""
    return price_checker.check_flight(flight_id)


def force_price_drop(flight_id, drop_percentage):
    """Wrapper for testing"""
    return price_checker.force_price_drop(flight_id, drop_percentage)