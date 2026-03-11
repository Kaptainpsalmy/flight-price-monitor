from .database import db
from datetime import datetime, timezone
from sqlalchemy import Index


class Flight(db.Model):
    __tablename__ = 'flights'

    id = db.Column(db.Integer, primary_key=True)

    # Flight identification
    flight_number = db.Column(db.String(20), nullable=False)
    airline = db.Column(db.String(50), nullable=False)

    # Route information
    origin = db.Column(db.String(3), nullable=False)  # Airport code
    destination = db.Column(db.String(3), nullable=False)  # Airport code

    # Dates
    departure_date = db.Column(db.DateTime, nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Price information
    original_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')

    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_cancelled = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alerts = db.relationship('PriceAlert', back_populates='flight', cascade='all, delete-orphan')
    price_history = db.relationship('PriceHistory', back_populates='flight', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        Index('idx_flight_active', 'is_active'),
        Index('idx_flight_departure', 'departure_date'),
        Index('idx_flight_number', 'flight_number'),
    )

    def __repr__(self):
        return f'<Flight {self.flight_number}: {self.origin}→{self.destination}>'

    @property
    def price_drop_percentage(self):
        """Calculate current price drop percentage"""
        if self.original_price == 0:
            return 0
        drop = ((self.original_price - self.current_price) / self.original_price) * 100
        return round(drop, 2)

    @property
    def days_until_departure(self):
        """Calculate days until departure"""
        # Make both dates naive or both aware
        if self.departure_date.tzinfo is not None:
            # departure_date is aware, aware now
            now = datetime.now(timezone.utc)
        else:
            # departure_date is naive, naive now
            now = datetime.utcnow()

        delta = self.departure_date - now
        return delta.days


class PriceAlert(db.Model):
    """Model representing price drop alerts that were triggered"""
    __tablename__ = 'price_alerts'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to flight
    flight_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=False)

    # Alert details
    alert_price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=False)
    drop_percentage = db.Column(db.Float, nullable=False)

    # Status
    alert_sent = db.Column(db.Boolean, default=True)  # For idempotency
    notification_method = db.Column(db.String(20), default='console')  # email, sms, webhook, etc.

    # Timestamps
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship back to flight
    flight = db.relationship('Flight', back_populates='alerts')

    # Indexes
    __table_args__ = (
        Index('idx_alert_flight', 'flight_id'),
        Index('idx_alert_triggered', 'triggered_at'),
    )

    def __repr__(self):
        return f'<PriceAlert Flight {self.flight_id}: {self.drop_percentage}% drop at ${self.alert_price}>'


class PriceHistory(db.Model):
    """Model tracking all price checks (for audit/history)"""
    __tablename__ = 'price_history'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to flight
    flight_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=False)

    # Price snapshot
    price = db.Column(db.Float, nullable=False)
    drop_percentage = db.Column(db.Float)

    # Check metadata
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(200))

    # Relationship back to flight
    flight = db.relationship('Flight', back_populates='price_history')

    # Indexes
    __table_args__ = (
        Index('idx_history_flight', 'flight_id'),
        Index('idx_history_checked', 'checked_at'),
    )

    def __repr__(self):
        return f'<PriceHistory Flight {self.flight_id}: ${self.price} at {self.checked_at}>'    