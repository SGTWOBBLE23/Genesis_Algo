#!/usr/bin/env python3
"""
Genesis Trading Platform - System Monitor
Provides Discord webhook alerts for critical system issues
"""
import logging
from app import app
from monitoring.system_monitor import run_monitoring_checks
from scheduler import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_monitoring_to_scheduler():
    """
    Add the monitoring job to the existing scheduler
    """
    try:
        # Use the existing scheduler module
        from scheduler import start_scheduler
        scheduler = start_scheduler()
        
        # Add the monitoring job to run every 5 minutes
        job = scheduler.add_job(
            run_monitoring_checks,
            CronTrigger(minute="*/5"),  # Run every 5 minutes
            id="discord_monitor",
            name="Monitor for critical system issues",
            replace_existing=True,
        )
        
        # Start the scheduler if not already running
        if not scheduler.running:
            scheduler.start()
            
        logger.info(f"Added system monitoring to scheduler: {job.name} (ID: {job.id})")
        logger.info(f"Next run time: {job.next_run_time}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add monitoring job: {e}")
        return False

def test_alerts():
    """Send a test alert to Discord webhook"""
    with app.app_context():
        from monitoring.discord_alerts import send_discord_alert
        
        success = send_discord_alert(
            title="Genesis Trading Monitor: Test Alert",
            description="This is a test alert from your Genesis Trading Platform.\n\n"
                      "If you're seeing this message, the Discord monitoring system is working correctly!\n\n"
                      "The monitor will alert you about:\n"
                      "• MT5 connection failures\n"
                      "• Trade discrepancies\n"
                      "• Exit system failures\n"
                      "• Critical database errors\n\n"
                      "Alert cooldown is set to 10 minutes.",
            alert_type="test",
            color=0x00FF00  # Green color for test message
        )
        
        if success:
            logger.info("Test alert sent successfully to Discord!")
        else:
            logger.error("Failed to send test alert to Discord.")
        
        return success

def run_now():
    """Run the monitoring checks immediately once"""
    with app.app_context():
        logger.info("Running system monitoring checks manually")
        run_monitoring_checks()
        logger.info("Monitoring checks completed")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Genesis Trading System Monitor")
    parser.add_argument("--test", action="store_true", help="Send a test alert and exit")
    parser.add_argument("--run", action="store_true", help="Run monitoring checks once and exit")
    parser.add_argument("--add", action="store_true", help="Add monitoring to scheduler")
    args = parser.parse_args()
    
    if args.test:
        test_alerts()
    elif args.run:
        run_now()
    elif args.add:
        add_monitoring_to_scheduler()
    else:
        # Default: run checks once and add to scheduler
        success = run_now()
        if success is not False:  # None or True means no explicit failure
            add_monitoring_to_scheduler()
            logger.info("Monitoring is now active and will run every 5 minutes")

if __name__ == "__main__":
    main()