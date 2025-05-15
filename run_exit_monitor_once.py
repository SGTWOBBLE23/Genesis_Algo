#!/usr/bin/env python3
"""
Run the exit monitor job once to test it.
This tests the integration between position_manager.py and the close_ticket API.
"""
import os
import sys
import logging
from app import app
from create_exit_monitor import monitor_trades_and_apply_exit_system

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Increase logging for key components
logging.getLogger('position_manager').setLevel(logging.DEBUG)
logging.getLogger('mt5_ea_api').setLevel(logging.DEBUG)
logging.getLogger('ml.exit_inference').setLevel(logging.DEBUG)

if __name__ == "__main__":
    # Set environment variable for debugging
    os.environ['DEBUG_EXIT_SYSTEM'] = 'true'
    
    with app.app_context():
        logger.info("Running exit monitor job once")
        try:
            # Run the monitor function
            monitor_trades_and_apply_exit_system()
            
            # Check if any tickets were added to the close queue
            from mt5_ea_api import pending_closures
            if pending_closures:
                logger.info(f"Success! Tickets were added to close queue: {pending_closures}")
            else:
                logger.warning("No tickets were added to the close queue")
                
            # Recommend next steps
            logger.info("Next steps:")
            logger.info("1. Verify MT5 EA is correctly polling the close queue endpoint")
            logger.info("2. Add this job to the scheduler to run automatically")
            logger.info("3. Consider adjusting the ExitNet threshold (currently 0.40)")
                
        except Exception as e:
            logger.error(f"Error running exit monitor: {e}")
            import traceback
            traceback.print_exc()