#!/usr/bin/env python3
"""
Add the Discord monitoring system to the scheduler
This integrates critical issue monitoring with webhook alerts
"""
import os
import logging
from app import app
from scheduler import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from discord_monitor import run_monitoring_checks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_discord_monitor_to_scheduler():
    """
    Add the Discord monitoring job to the existing scheduler
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
            
        logger.info(f"Added Discord monitoring job to scheduler: {job.name} (ID: {job.id})")
        logger.info(f"Next run time: {job.next_run_time}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add Discord monitoring job: {e}")
        return False

def run_now():
    """Run the monitoring checks immediately once"""
    try:
        with app.app_context():
            logger.info("Running Discord monitoring checks immediately")
            run_monitoring_checks()
        return True
    except Exception as e:
        logger.error(f"Failed to run Discord monitoring checks: {e}")
        return False

if __name__ == "__main__":
    # Run the job once immediately
    success = run_now()
    
    # Also add it to the scheduler
    if success:
        added = add_discord_monitor_to_scheduler()
        if added:
            logger.info("Discord monitoring job has been added to the scheduler")
            logger.info("It will now run automatically every 5 minutes")
        else:
            logger.error("Failed to add Discord monitoring to scheduler")
    else:
        logger.error("Initial run failed, not adding to scheduler")