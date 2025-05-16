#!/usr/bin/env python3
"""
Force run all monitoring checks immediately
Use this script to manually check system status at any time
"""
import logging
from app import app
from discord_monitor import run_monitoring_checks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Manually running all system monitoring checks")
    
    with app.app_context():
        # Run all checks and force alert if issues are found (regardless of cooldown)
        try:
            # Run the standard monitoring function
            run_monitoring_checks()
            logger.info("Monitoring checks completed")
            
        except Exception as e:
            logger.error(f"Error running monitoring checks: {e}")
            
    logger.info("Check complete. Any issues will trigger alerts in Discord.")