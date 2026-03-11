#!/usr/bin/env python
"""
Entry point for the Price Monitor microservice
"""
from app import create_app
from app.scheduler import start_scheduler
import sys
import argparse

app = create_app()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Price Monitor service')
    parser.add_argument('--with-scheduler', action='store_true',
                        help='Start the scheduler for periodic price checks')
    parser.add_argument('--port', type=int, default=5001,
                        help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', default=True,
                        help='Run in debug mode')

    args = parser.parse_args()

    # Start scheduler if requested
    if args.with_scheduler:
        print("Starting scheduler...")
        start_scheduler(app)

    # Run the Flask app
    app.run(debug=args.debug, host='0.0.0.0', port=args.port)