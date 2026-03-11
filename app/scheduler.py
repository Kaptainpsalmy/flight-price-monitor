from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from flask import current_app
from .price_checker import price_checker
from .logger import setup_logger
from datetime import datetime
import atexit
import traceback

# Setup logger
logger = setup_logger('scheduler')

class PriceMonitorScheduler:
    def __init__(self):
        self.scheduler = None
        self.is_running = False
        self.job_id = 'price_check_job'
        self.logger = logger

    def init_scheduler(self, app):
        """Initialize the scheduler with app context"""
        try:
            # Configure executors and job stores
            executors = {
                'default': ThreadPoolExecutor(20)  # 20 concurrent threads
            }

            jobstores = {
                'default': MemoryJobStore()
            }

            # Create scheduler
            self.scheduler = BackgroundScheduler(
                executors=executors,
                jobstores=jobstores,
                timezone='UTC'
            )

            # Store app reference for context
            self.app = app

            self.logger.info("✅ Scheduler initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize scheduler: {str(e)}")
            self.logger.error(traceback.format_exc())

    def start(self, app=None):
        """Start the scheduler"""
        try:
            if app:
                self.init_scheduler(app)

            if not self.scheduler:
                self.logger.error("Cannot start scheduler: not initialized")
                return False

            if self.is_running:
                self.logger.warning("Scheduler is already running")
                return True

            # Get check interval from config
            with self.app.app_context():
                interval_minutes = current_app.config.get('PRICE_CHECK_INTERVAL_MINUTES', 1)
                interval_hours = current_app.config.get('PRICE_CHECK_INTERVAL_HOURS', None)

            # Determine trigger type
            if interval_minutes:
                trigger = IntervalTrigger(minutes=interval_minutes)
                trigger_desc = f"every {interval_minutes} minute{'s' if interval_minutes > 1 else ''}"
            elif interval_hours:
                trigger = IntervalTrigger(hours=interval_hours)
                trigger_desc = f"every {interval_hours} hour{'s' if interval_hours > 1 else ''}"
            else:
                # Default to every hour
                trigger = IntervalTrigger(hours=1)
                trigger_desc = "every 1 hour"

            # Add job
            self.scheduler.add_job(
                func=self.run_price_check,
                trigger=trigger,
                id=self.job_id,
                name=f"Price Check - {trigger_desc}",
                replace_existing=True,
                misfire_grace_time=30,  # Allow 30 seconds grace for misfired jobs
                coalesce=True  # Combine missed executions into one
            )

            # Start scheduler
            self.scheduler.start()
            self.is_running = True

            self.logger.info(f"✅ Scheduler started - checking prices {trigger_desc}")

            # Register shutdown
            atexit.register(self.shutdown)

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start scheduler: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    def run_price_check(self):
        """
        Job function that runs price checks
        This runs in the scheduler's thread pool
        """
        try:
            self.logger.info("⏰ Scheduled price check triggered")

            # Run in app context
            with self.app.app_context():
                start_time = datetime.utcnow()

                # Run the price check
                results = price_checker.check_all_flights()

                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()

                self.logger.info(f"✅ Scheduled price check completed in {duration:.2f} seconds")
                self.logger.info(f"   Results: {results}")

                # Log to a separate file for monitoring
                self.log_scheduled_check(results, duration)

        except Exception as e:
            self.logger.error(f"❌ Error in scheduled price check: {str(e)}")
            self.logger.error(traceback.format_exc())

    def log_scheduled_check(self, results, duration):
        """Log scheduled check results to a separate file"""
        try:
            with open('logs/scheduler.log', 'a') as f:
                f.write(f"{datetime.utcnow().isoformat()} | Duration: {duration:.2f}s | "
                       f"Total: {results.get('total', 0)} | "
                       f"Success: {results.get('successful', 0)} | "
                       f"Failed: {results.get('failed', 0)} | "
                       f"Alerts: {results.get('alerts_triggered', 0)}\n")
        except:
            pass  # Don't let logging errors break the scheduler

    def stop(self):
        """Stop the scheduler"""
        try:
            if self.scheduler and self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                self.logger.info("⏹️ Scheduler stopped")
                return True
        except Exception as e:
            self.logger.error(f"Error stopping scheduler: {str(e)}")
            return False

    def shutdown(self):
        """Clean shutdown (called at exit)"""
        self.stop()

    def get_status(self):
        """Get current scheduler status"""
        if not self.scheduler or not self.is_running:
            return {
                'running': False,
                'message': 'Scheduler is not running'
            }

        jobs = self.scheduler.get_jobs()
        next_run_time = None

        for job in jobs:
            if job.id == self.job_id:
                next_run_time = job.next_run_time.isoformat() if job.next_run_time else None
                break

        return {
            'running': True,
            'next_run': next_run_time,
            'job_id': self.job_id,
            'total_jobs': len(jobs)
        }

    def trigger_manual_check(self):
        """
        Manually trigger a price check (outside schedule)
        Returns: (success: bool, message: str, results: dict)
        """
        self.logger.info("👆 Manual price check triggered")

        try:
            with self.app.app_context():
                results = price_checker.check_all_flights()

                return True, "Manual price check completed", results

        except Exception as e:
            self.logger.error(f"Error in manual price check: {str(e)}")
            return False, str(e), None


# Create singleton instance
scheduler_manager = PriceMonitorScheduler()


# Convenience functions
def start_scheduler(app):
    """Start the scheduler (called from run.py)"""
    return scheduler_manager.start(app)

def stop_scheduler():
    """Stop the scheduler"""
    return scheduler_manager.stop()

def trigger_manual_check():
    """Manually trigger a price check"""
    return scheduler_manager.trigger_manual_check()

def get_scheduler_status():
    """Get scheduler status"""
    return scheduler_manager.get_status()