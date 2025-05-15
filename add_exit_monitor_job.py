#!/usr/bin/env python3
"""
Add the exit monitor to the scheduler system
This will integrate the position_manager.py functionality into the regular job system
"""
import os
import logging
from app import app
from scheduler import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from create_exit_monitor import monitor_trades_and_apply_exit_system

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_exit_monitor_to_scheduler():
    """
    Add the exit monitor job to the existing scheduler
    """
    try:
        # Use the existing scheduler module
        from scheduler import start_scheduler
        scheduler = start_scheduler()
        
        # Add the exit monitor job to run every 15 minutes
        job = scheduler.add_job(
            monitor_trades_and_apply_exit_system,
            IntervalTrigger(minutes=15),
            id="exit_monitor",
            name="Monitor trades for exit signals every 15 minutes",
            replace_existing=True,
        )
        
        # Start the scheduler if not already running
        if not scheduler.running:
            scheduler.start()
            
        logger.info(f"Added exit monitor job to scheduler: {job.name} (ID: {job.id})")
        logger.info(f"Next run time: {job.next_run_time}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add exit monitor job: {e}")
        return False

def run_now():
    """Run the exit monitor job immediately once"""
    try:
        with app.app_context():
            logger.info("Running exit monitor job immediately")
            monitor_trades_and_apply_exit_system()
        return True
    except Exception as e:
        logger.error(f"Failed to run exit monitor job: {e}")
        return False

if __name__ == "__main__":
    # Run the job once immediately
    success = run_now()
    
    # Also add it to the scheduler
    if success:
        added = add_exit_monitor_to_scheduler()
        if added:
            logger.info("Exit monitor job has been added to the scheduler")
            logger.info("It will now run automatically every 15 minutes")
        else:
            logger.error("Failed to add exit monitor to scheduler")
    else:
        logger.error("Initial run failed, not adding to scheduler")