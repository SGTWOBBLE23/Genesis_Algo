import os
import logging
from datetime import datetime
from typing import List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import capture_job
from config import ASSETS              # 👈 unified list

logger = logging.getLogger(__name__)


def capture_all_assets():
    """Run capture job for all configured assets"""
    logger.info(f"Running capture job for all {len(ASSETS)} assets")
    for symbol in ASSETS:
        try:
            logger.info(f"Capturing {symbol}")
            capture_job.run(symbol)
        except Exception as e:
            logger.error(f"Error capturing {symbol}: {str(e)}")


def capture_hourly_assets():
    """Run capture job for all assets at top of the hour (for 1H timeframe)"""
    logger.info(f"Running hourly capture job for all {len(ASSETS)} assets")
    for symbol in ASSETS:
        try:
            logger.info(f"Capturing hourly chart for {symbol}")
            capture_job.run(symbol, datetime.now())
        except Exception as e:
            logger.error(f"Error capturing hourly chart for {symbol}: {str(e)}")


def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule 15-minute capture jobs
    scheduler.add_job(
        capture_all_assets,
        CronTrigger(minute='*/15'),  # Every 15 minutes
        id='capture_15m',
        name='Capture all assets every 15 minutes',
        replace_existing=True
    )
    
    # Schedule hourly capture jobs
    scheduler.add_job(
        capture_hourly_assets,
        CronTrigger(minute='0'),  # At the top of every hour
        id='capture_1h',
        name='Capture all assets hourly for 1H timeframe',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started with 15-minute and hourly capture jobs")
    
    return scheduler


if __name__ == "__main__":
    # Test the scheduler
    logging.basicConfig(level=logging.INFO)
    scheduler = start_scheduler()
    
    try:
        # Run once for testing
        logger.info("Running a test capture")
        capture_all_assets()
        
        # Keep the script running to allow scheduled jobs to execute
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
