from flask import Flask, jsonify, request, url_for
from .config import get_config
from .database import db, init_db
from .scheduler import scheduler_manager, trigger_manual_check, get_scheduler_status
from .price_checker import check_single_price, force_price_drop, price_checker
from .models import Flight, PriceAlert, PriceHistory
from .validation import validate_flight_data, validate_pagination, validate_date_range
from datetime import datetime, timedelta
import traceback
from sqlalchemy import desc, func
import json

def create_app():
    app = Flask(__name__)

    # i loaded configuration
    app.config.from_object(get_config())

    init_db(app)

    app.scheduler_manager = scheduler_manager

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'message': 'Bad request',
            'error': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'message': 'Resource not found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error': str(error) if app.debug else 'An unexpected error occurred'
        }), 500

    # JSON decode error handler
    @app.before_request
    def handle_json_errors():
        """Catch JSON decode errors before they crash"""
        if request.is_json:
            try:
                _ = request.get_json()
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': 'Invalid JSON format',
                    'error': str(e)
                }), 400

    @app.route('/health')
    def health():
        try:
            db.engine.connect()

            scheduler_status = get_scheduler_status()

            # Get counts for monitoring
            flight_count = Flight.query.count()
            active_flight_count = Flight.query.filter_by(is_active=True).count()
            alert_count = PriceAlert.query.count()

            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'scheduler': scheduler_status,
                'environment': app.config.get('ENV', 'development'),
                'service': 'price-monitor',
                'stats': {
                    'total_flights': flight_count,
                    'active_flights': active_flight_count,
                    'total_alerts': alert_count
                }
            }), 200
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'disconnected',
                'scheduler': get_scheduler_status(),
                'environment': app.config.get('ENV', 'development'),
                'error': str(e)
            }), 500

    @app.route('/')
    def index():
        return jsonify({
            'name': 'Price Monitor Microservice',
            'version': '1.0.0',
            'environment': app.config.get('ENV', 'development'),
            'description': 'Monitors flight prices and triggers alerts on 10%+ drops',
            'documentation': {
                'html': 'https://github.com/yourusername/price-monitor#readme',
                'postman_collection': '/api/docs/postman',
                'openapi_json': '/api/docs/openapi.json'
            },
            'settings': {
                'price_check_interval_minutes': app.config.get('PRICE_CHECK_INTERVAL_MINUTES', 1),
                'alert_threshold_percent': app.config.get('ALERT_THRESHOLD_PERCENT', 10)
            },
            'endpoints': {
                'GET /health': 'Health check with system stats',
                'GET /': 'This documentation',

                # Scheduler
                'GET /api/scheduler/status': 'Get scheduler status',
                'POST /api/scheduler/start': 'Start the scheduler',
                'POST /api/scheduler/stop': 'Stop the scheduler',
                'POST /api/scheduler/trigger': 'Manually trigger a price check',

                # Flight
                'GET /api/flights': 'List all flights (with filters)',
                'POST /api/flights': 'Add a new flight to monitor',
                'GET /api/flights/<id>': 'Get flight details',
                'PUT /api/flights/<id>': 'Update flight',
                'DELETE /api/flights/<id>': 'Stop monitoring a flight',
                'POST /api/flights/<id>/check': 'Manually check flight price',
                'POST /api/flights/<id>/force-drop': 'Force price drop (testing)',
                'GET /api/flights/<id>/history': 'Get price history',

                # Alert
                'GET /api/alerts': 'List all alerts',
                'GET /api/alerts/<id>': 'Get alert details',
                'GET /api/flights/<id>/alerts': 'Get alerts for a flight',

                # Stats
                'GET /api/stats/summary': 'Get summary statistics',
                'GET /api/stats/trends': 'Get price trend analysis',


            }
        })


    # ========== SCHEDULER API ENDPOINTS ==========

    @app.route('/api/scheduler/status', methods=['GET'])
    def scheduler_status():
        """scheduler status"""
        return jsonify(get_scheduler_status())

    @app.route('/api/scheduler/start', methods=['POST'])
    def scheduler_start():
        """Start the scheduler"""
        try:
            status = get_scheduler_status()
            if status.get('running'):
                return jsonify({
                    'success': True,
                    'message': 'Scheduler is already running',
                    'status': status
                }), 200

            # Start scheduler
            success = scheduler_manager.start(app)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Scheduler started successfully',
                    'status': get_scheduler_status()
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to start scheduler',
                    'status': get_scheduler_status()
                }), 500

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}',
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/scheduler/stop', methods=['POST'])
    def scheduler_stop():
        """Stop the scheduler"""
        try:
            success = scheduler_manager.stop()

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Scheduler stopped successfully',
                    'status': get_scheduler_status()
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to stop scheduler or scheduler not running',
                    'status': get_scheduler_status()
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/scheduler/trigger', methods=['POST'])
    def scheduler_trigger():

        try:
            success, message, results = trigger_manual_check()

            if success:
                return jsonify({
                    'success': True,
                    'message': message,
                    'results': results
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': message
                }), 500

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    # ========== FLIGHT API ENDPOINTS ==========

    @app.route('/api/flights', methods=['GET'])
    def get_flights():
        try:
            # Validate pagination parameters
            pagination_errors = validate_pagination(request.args)
            if pagination_errors:
                return jsonify({
                    'success': False,
                    'errors': pagination_errors
                }), 400

            # query parameters
            active_only = request.args.get('active_only', 'false').lower() == 'true'
            flight_number = request.args.get('flight_number')
            origin = request.args.get('origin')
            destination = request.args.get('destination')
            airline = request.args.get('airline')
            min_price = request.args.get('min_price')
            max_price = request.args.get('max_price')
            min_drop = request.args.get('min_drop')

            # Pagination
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))

            query = Flight.query

            if active_only:
                query = query.filter_by(is_active=True)

            if flight_number:
                query = query.filter(Flight.flight_number.ilike(f'%{flight_number}%'))

            if origin:
                query = query.filter(Flight.origin == origin.upper())

            if destination:
                query = query.filter(Flight.destination == destination.upper())

            if airline:
                query = query.filter(Flight.airline.ilike(f'%{airline}%'))

            if min_price:
                query = query.filter(Flight.current_price >= float(min_price))

            if max_price:
                query = query.filter(Flight.current_price <= float(max_price))

            paginated = query.order_by(Flight.departure_date).paginate(
                page=page, per_page=per_page, error_out=False
            )

            flights = paginated.items

            if min_drop:
                min_drop = float(min_drop)
                flights = [f for f in flights if f.price_drop_percentage >= min_drop]

            # Build response
            return jsonify({
                'success': True,
                'count': len(flights),
                'total': paginated.total,
                'page': page,
                'pages': paginated.pages,
                'per_page': per_page,
                'flights': [{
                    'id': f.id,
                    'flight_number': f.flight_number,
                    'airline': f.airline,
                    'origin': f.origin,
                    'destination': f.destination,
                    'departure_date': f.departure_date.isoformat(),
                    'original_price': f.original_price,
                    'current_price': f.current_price,
                    'drop_percentage': f.price_drop_percentage,
                    'days_until_departure': f.days_until_departure,
                    'is_active': f.is_active,
                    'is_cancelled': f.is_cancelled,
                    'alert_count': len(f.alerts),
                    'last_checked': f.last_checked.isoformat() if f.last_checked else None,
                    'created_at': f.created_at.isoformat() if f.created_at else None,
                    'links': {
                        'self': url_for('get_flight', flight_id=f.id, _external=True),
                        'alerts': url_for('get_flight_alerts', flight_id=f.id, _external=True),
                        'history': url_for('get_flight_history', flight_id=f.id, _external=True)
                    }
                } for f in flights]
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights', methods=['POST'])
    def create_flight():
        """Add a new flight to monitor"""
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    'success': False,
                    'message': 'No data provided'
                }), 400

            # Validate input
            errors = validate_flight_data(data)
            if errors:
                return jsonify({
                    'success': False,
                    'errors': errors
                }), 400

            # Parse departure date
            departure_date = datetime.fromisoformat(data['departure_date'].replace('Z', '+00:00'))

            # Create flight
            flight = Flight(
                flight_number=data['flight_number'].upper(),
                airline=data['airline'],
                origin=data['origin'].upper(),
                destination=data['destination'].upper(),
                departure_date=departure_date,
                original_price=float(data['original_price']),
                current_price=float(data['original_price']),  # Start at original price
                currency=data.get('currency', 'USD'),
                is_active=True
            )

            db.session.add(flight)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Flight created successfully',
                'flight': {
                    'id': flight.id,
                    'flight_number': flight.flight_number,
                    'links': {
                        'self': url_for('get_flight', flight_id=flight.id, _external=True)
                    }
                }
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>', methods=['GET'])
    def get_flight(flight_id):
        """Get specific flight details"""
        try:
            flight = Flight.query.get(flight_id)

            if not flight:
                return jsonify({
                    'success': False,
                    'message': f'Flight {flight_id} not found'
                }), 404

            # Get alerts for this flight
            alerts = PriceAlert.query.filter_by(flight_id=flight.id)\
                .order_by(PriceAlert.triggered_at.desc())\
                .limit(10)\
                .all()

            return jsonify({
                'success': True,
                'flight': {
                    'id': flight.id,
                    'flight_number': flight.flight_number,
                    'airline': flight.airline,
                    'origin': flight.origin,
                    'destination': flight.destination,
                    'departure_date': flight.departure_date.isoformat(),
                    'original_price': flight.original_price,
                    'current_price': flight.current_price,
                    'drop_percentage': flight.price_drop_percentage,
                    'days_until_departure': flight.days_until_departure,
                    'is_active': flight.is_active,
                    'is_cancelled': flight.is_cancelled,
                    'currency': flight.currency,
                    'created_at': flight.created_at.isoformat() if flight.created_at else None,
                    'updated_at': flight.updated_at.isoformat() if flight.updated_at else None,
                    'last_checked': flight.last_checked.isoformat() if flight.last_checked else None,
                    'stats': {
                        'total_alerts': len(flight.alerts),
                        'total_price_checks': len(flight.price_history)
                    },
                    'recent_alerts': [{
                        'id': a.id,
                        'price': a.alert_price,
                        'drop_percentage': a.drop_percentage,
                        'triggered_at': a.triggered_at.isoformat()
                    } for a in alerts],
                    'links': {
                        'self': url_for('get_flight', flight_id=flight.id, _external=True),
                        'alerts': url_for('get_flight_alerts', flight_id=flight.id, _external=True),
                        'history': url_for('get_flight_history', flight_id=flight.id, _external=True),
                        'check': url_for('check_flight_manual', flight_id=flight.id, _external=True)
                    }
                }
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>', methods=['PUT'])
    def update_flight(flight_id):
        """Update flight details"""
        try:
            flight = Flight.query.get(flight_id)

            if not flight:
                return jsonify({
                    'success': False,
                    'message': f'Flight {flight_id} not found'
                }), 404

            data = request.get_json()

            if not data:
                return jsonify({
                    'success': False,
                    'message': 'No data provided'
                }), 400

            # Update allowed fields
            updatable_fields = ['is_active', 'is_cancelled']

            for field in updatable_fields:
                if field in data:
                    setattr(flight, field, data[field])

            # Special handling for departure date
            if 'departure_date' in data:
                try:
                    flight.departure_date = datetime.fromisoformat(data['departure_date'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return jsonify({
                        'success': False,
                        'message': 'Invalid departure_date format'
                    }), 400

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Flight updated successfully',
                'flight': {
                    'id': flight.id,
                    'flight_number': flight.flight_number,
                    'is_active': flight.is_active,
                    'is_cancelled': flight.is_cancelled
                }
            }), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>', methods=['DELETE'])
    def delete_flight(flight_id):
        """Stop monitoring a flight (soft delete)"""
        try:
            flight = Flight.query.get(flight_id)

            if not flight:
                return jsonify({
                    'success': False,
                    'message': f'Flight {flight_id} not found'
                }), 404

            # Soft delete - just mark as inactive
            flight.is_active = False
            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Flight {flight_id} deactivated'
            }), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>/check', methods=['POST'])
    def check_flight_manual(flight_id):
        """Manually check price for a specific flight"""
        try:
            success, message, data = check_single_price(flight_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': data
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>/force-drop', methods=['POST'])
    def force_flight_drop(flight_id):
        """Force a price drop for testing """
        try:
            data = request.get_json() or {}
            drop_percentage = data.get('drop_percentage', 10)

            if drop_percentage < 0 or drop_percentage > 50:
                return jsonify({
                    'success': False,
                    'message': 'Drop percentage must be between 0 and 50'
                }), 400

            success, message, result = force_price_drop(flight_id, drop_percentage)

            if success:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': result
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>/history', methods=['GET'])
    def get_flight_history(flight_id):
        """price history for a flight"""
        try:
            flight = Flight.query.get(flight_id)

            if not flight:
                return jsonify({
                    'success': False,
                    'message': f'Flight {flight_id} not found'
                }), 404

            # history with pagination
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 30))

            history = PriceHistory.query.filter_by(flight_id=flight_id)\
                .order_by(PriceHistory.checked_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)

            return jsonify({
                'success': True,
                'flight_id': flight_id,
                'flight_number': flight.flight_number,
                'total': history.total,
                'page': page,
                'pages': history.pages,
                'history': [{
                    'id': h.id,
                    'price': h.price,
                    'drop_percentage': h.drop_percentage,
                    'checked_at': h.checked_at.isoformat(),
                    'notes': h.notes
                } for h in history.items]
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500


    @app.route('/api/alerts', methods=['GET'])
    def get_alerts():
        """Get all alerts with filters"""
        try:
            # Query parameters
            flight_id = request.args.get('flight_id')
            days = request.args.get('days', type=int)
            min_drop = request.args.get('min_drop', type=float)

            # Build query
            query = PriceAlert.query

            if flight_id:
                query = query.filter_by(flight_id=flight_id)

            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(PriceAlert.triggered_at >= cutoff)

            if min_drop:
                query = query.filter(PriceAlert.drop_percentage >= min_drop)

            # Pagination
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))

            paginated = query.order_by(PriceAlert.triggered_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)

            return jsonify({
                'success': True,
                'count': len(paginated.items),
                'total': paginated.total,
                'page': page,
                'pages': paginated.pages,
                'alerts': [{
                    'id': a.id,
                    'flight_id': a.flight_id,
                    'flight_number': a.flight.flight_number if a.flight else None,
                    'alert_price': a.alert_price,
                    'original_price': a.original_price,
                    'drop_percentage': a.drop_percentage,
                    'triggered_at': a.triggered_at.isoformat(),
                    'links': {
                        'self': url_for('get_alert', alert_id=a.id, _external=True),
                        'flight': url_for('get_flight', flight_id=a.flight_id, _external=True)
                    }
                } for a in paginated.items]
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/alerts/<int:alert_id>', methods=['GET'])
    def get_alert(alert_id):
        """Get specific alert details"""
        try:
            alert = PriceAlert.query.get(alert_id)

            if not alert:
                return jsonify({
                    'success': False,
                    'message': f'Alert {alert_id} not found'
                }), 404

            flight = Flight.query.get(alert.flight_id)

            return jsonify({
                'success': True,
                'alert': {
                    'id': alert.id,
                    'flight': {
                        'id': flight.id,
                        'flight_number': flight.flight_number,
                        'airline': flight.airline,
                        'origin': flight.origin,
                        'destination': flight.destination
                    } if flight else None,
                    'alert_price': alert.alert_price,
                    'original_price': alert.original_price,
                    'drop_percentage': alert.drop_percentage,
                    'triggered_at': alert.triggered_at.isoformat(),
                    'notification_method': alert.notification_method
                }
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/flights/<int:flight_id>/alerts', methods=['GET'])
    def get_flight_alerts(flight_id):
        """Get alerts for a specific flight"""
        try:
            flight = Flight.query.get(flight_id)

            if not flight:
                return jsonify({
                    'success': False,
                    'message': f'Flight {flight_id} not found'
                }), 404

            # Get alerts with pagination
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))

            alerts = PriceAlert.query.filter_by(flight_id=flight_id)\
                .order_by(PriceAlert.triggered_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)

            return jsonify({
                'success': True,
                'flight_id': flight_id,
                'flight_number': flight.flight_number,
                'total': alerts.total,
                'page': page,
                'pages': alerts.pages,
                'alerts': [{
                    'id': a.id,
                    'alert_price': a.alert_price,
                    'drop_percentage': a.drop_percentage,
                    'triggered_at': a.triggered_at.isoformat()
                } for a in alerts.items]
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    # ========== STATISTICS ENDPOINTS ==========

    @app.route('/api/stats/summary', methods=['GET'])
    def get_stats_summary():
        """summary statistics"""
        try:
            # Basic counts
            total_flights = Flight.query.count()
            active_flights = Flight.query.filter_by(is_active=True).count()
            total_alerts = PriceAlert.query.count()

            # Alerts today
            today = datetime.utcnow().date()
            alerts_today = PriceAlert.query.filter(
                func.date(PriceAlert.triggered_at) == today
            ).count()

            # Average drop percentage
            avg_drop = db.session.query(func.avg(PriceAlert.drop_percentage)).scalar() or 0

            # Biggest drop
            biggest_drop = PriceAlert.query.order_by(PriceAlert.drop_percentage.desc()).first()

            # Most active flight
            most_active = db.session.query(
                Flight.flight_number,
                func.count(PriceAlert.id).label('alert_count')
            ).join(PriceAlert).group_by(Flight.id, Flight.flight_number)\
             .order_by(desc('alert_count')).first()

            return jsonify({
                'success': True,
                'timestamp': datetime.utcnow().isoformat(),
                'statistics': {
                    'flights': {
                        'total': total_flights,
                        'active': active_flights,
                        'inactive': total_flights - active_flights
                    },
                    'alerts': {
                        'total': total_alerts,
                        'today': alerts_today,
                        'average_drop_percentage': round(float(avg_drop), 2) if avg_drop else 0
                    },
                    'highlights': {
                        'biggest_drop': {
                            'flight': biggest_drop.flight.flight_number if biggest_drop else None,
                            'drop_percentage': biggest_drop.drop_percentage if biggest_drop else None,
                            'price': biggest_drop.alert_price if biggest_drop else None
                        } if biggest_drop else None,
                        'most_alerted_flight': {
                            'flight_number': most_active[0] if most_active else None,
                            'alert_count': most_active[1] if most_active else 0
                        } if most_active else None
                    }
                }
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    @app.route('/api/stats/trends', methods=['GET'])
    def get_price_trends():
        """price trend analysis"""
        try:
            days = int(request.args.get('days', 30))

            if days > 365:
                return jsonify({
                    'success': False,
                    'message': 'Maximum days is 365'
                }), 400

            cutoff = datetime.utcnow() - timedelta(days=days)

            # alerts in date range
            alerts = PriceAlert.query.filter(
                PriceAlert.triggered_at >= cutoff
            ).order_by(PriceAlert.triggered_at).all()

            from collections import defaultdict
            daily_counts = defaultdict(int)
            daily_drops = defaultdict(list)

            for alert in alerts:
                date_str = alert.triggered_at.date().isoformat()
                daily_counts[date_str] += 1
                daily_drops[date_str].append(alert.drop_percentage)

            # Build trend data
            trend_data = []
            for date_str in sorted(daily_counts.keys()):
                drops = daily_drops[date_str]
                trend_data.append({
                    'date': date_str,
                    'alert_count': daily_counts[date_str],
                    'avg_drop': round(sum(drops) / len(drops), 2) if drops else 0,
                    'min_drop': min(drops) if drops else 0,
                    'max_drop': max(drops) if drops else 0
                })

            return jsonify({
                'success': True,
                'period_days': days,
                'total_alerts': len(alerts),
                'trends': trend_data
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500

    return app