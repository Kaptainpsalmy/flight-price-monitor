from app import create_app
from app.scheduler import start_scheduler
import argparse

app = create_app()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Flight Price Monitor - Tracks flight prices and sends alerts'
    )

    #enable automatic price checking
    parser.add_argument('--with-scheduler',
                        action='store_true',
                        help='Turn on automatic price checks (runs in background)')

    # Which port should the app listen on? Defaulting to 5001 to avoid conflicts
    parser.add_argument('--port',
                        type=int,
                        default=5001,
                        help='Port number for the server (default: 5001)')

    # Debug mode gives us helpful error messages during development
    parser.add_argument('--debug',
                        action='store_true',
                        default=True,
                        help='Run in debug mode (more detailed errors)')

    # Parse the arguments the user passed in
    args = parser.parse_args()

    # If they want the scheduler, start it up before the main app
    if args.with_scheduler:
        print("🔧 Initializing price checker scheduler...")
        print("   The system will now automatically check flight prices")
        start_scheduler(app)

    print(f"\n🚀 Flight Price Monitor starting up...")
    print(f"   Server will be available at: http://localhost:{args.port}")
    print(f"   Debug mode: {'ON' if args.debug else 'OFF'}")
    print(f"   Automatic price checks: {'ENABLED' if args.with_scheduler else 'DISABLED'}")
    print("\n📝 Press Ctrl+C to stop the server\n")

    # Fire it up!
    app.run(
        debug=args.debug,
        host='0.0.0.0',
        port=args.port
    )