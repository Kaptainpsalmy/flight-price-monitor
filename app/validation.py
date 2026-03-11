"""
Request validation for API endpoints
"""
from flask import request
from datetime import datetime
import re


def validate_flight_data(data):
    """Validate flight creation/update data"""
    errors = []

    # Flight number (required)
    if not data.get('flight_number'):
        errors.append("flight_number is required")
    elif not isinstance(data['flight_number'], str):
        errors.append("flight_number must be a string")
    elif len(data['flight_number']) > 20:
        errors.append("flight_number must be less than 20 characters")

    # Airline (required)
    if not data.get('airline'):
        errors.append("airline is required")
    elif not isinstance(data['airline'], str):
        errors.append("airline must be a string")

    # Origin (required)
    if not data.get('origin'):
        errors.append("origin is required")
    elif not isinstance(data['origin'], str):
        errors.append("origin must be a string")
    elif not re.match(r'^[A-Z]{3}$', data['origin']):
        errors.append("origin must be a 3-letter airport code (e.g., JFK)")

    # Destination (required)
    if not data.get('destination'):
        errors.append("destination is required")
    elif not isinstance(data['destination'], str):
        errors.append("destination must be a string")
    elif not re.match(r'^[A-Z]{3}$', data['destination']):
        errors.append("destination must be a 3-letter airport code (e.g., LAX)")

    # Departure date (required)
    if not data.get('departure_date'):
        errors.append("departure_date is required")
    else:
        try:
            # Try to parse the date
            if isinstance(data['departure_date'], str):
                departure_date = datetime.fromisoformat(data['departure_date'].replace('Z', '+00:00'))
            else:
                departure_date = data['departure_date']

            # Check if date is in the future
            if departure_date < datetime.now():
                errors.append("departure_date must be in the future")
        except (ValueError, TypeError):
            errors.append("departure_date must be a valid ISO format date (e.g., 2026-04-15T10:30:00)")

    # Original price (required)
    if data.get('original_price') is None:
        errors.append("original_price is required")
    else:
        try:
            price = float(data['original_price'])
            if price <= 0:
                errors.append("original_price must be greater than 0")
        except (ValueError, TypeError):
            errors.append("original_price must be a number")

    # Currency (optional)
    if data.get('currency'):
        if not isinstance(data['currency'], str):
            errors.append("currency must be a string")
        elif not re.match(r'^[A-Z]{3}$', data['currency']):
            errors.append("currency must be a 3-letter code (e.g., USD)")

    return errors


def validate_pagination(args):
    """Validate pagination parameters"""
    errors = []

    # Page
    if args.get('page'):
        try:
            page = int(args['page'])
            if page < 1:
                errors.append("page must be at least 1")
        except ValueError:
            errors.append("page must be an integer")

    # Per page
    if args.get('per_page'):
        try:
            per_page = int(args['per_page'])
            if per_page < 1 or per_page > 100:
                errors.append("per_page must be between 1 and 100")
        except ValueError:
            errors.append("per_page must be an integer")

    return errors


def validate_date_range(args):
    """Validate date range parameters"""
    errors = []

    # Start date
    if args.get('start_date'):
        try:
            datetime.fromisoformat(args['start_date'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            errors.append("start_date must be a valid ISO format date")

    # End date
    if args.get('end_date'):
        try:
            datetime.fromisoformat(args['end_date'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            errors.append("end_date must be a valid ISO format date")

    return errors