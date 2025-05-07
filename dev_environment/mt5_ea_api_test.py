"""
Test version of the MT5 EA API module
This file wraps the original mt5_ea_api.py with test-specific modifications
"""

import logging
import json
import time
import sys
import os
from datetime import datetime
from functools import wraps

# Add parent directory to path to allow imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now we can import Flask and other dependencies
from flask import request, jsonify

# Set up logging for test environment
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Import the original module
from mt5_ea_api import *

# Check if we're in test mode
try:
    from config_test import TEST_MODE, TEST_ENVIRONMENT
except ImportError:
    TEST_MODE = True
    TEST_ENVIRONMENT = True

# Print banner for test mode
if TEST_MODE:
    logger.info("="*60)
    logger.info("MT5 EA API running in TEST MODE - No signals will be sent to MT5")
    logger.info("This environment is for testing only")
    logger.info("="*60)

# Create a decorator to modify behavior of functions in test mode
def test_mode_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Log the function call for debugging
        logger.info(f"[TEST] Called function: {func.__name__}")
        
        # Call the original function
        result = func(*args, **kwargs)
        
        # If this is a signal-related function, log what would happen
        if func.__name__ in ['get_signals', 'execute_signal', 'heartbeat']:
            logger.info(f"[TEST] Function {func.__name__} executed in TEST mode - no actual MT5 communication")
            
            # Add test tag to response if it's JSON
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
                # It's a Flask response with a JSON dict and status code
                response_dict, status_code = result
                if isinstance(response_dict, dict):
                    response_dict['test_mode'] = True
                    response_dict['warning'] = "Running in TEST mode - no actual MT5 communication"
                return response_dict, status_code
            
        return result
    return wrapper

# Override key functions with test behavior
@test_mode_wrapper
def get_signals():
    """TEST MODE: Process signals but don't send to MT5"""
    # Import the get_signals function from the original module
    from mt5_ea_api import get_signals as original_get_signals
    
    result = original_get_signals()
    logger.info(f"[TEST] get_signals would send {len(result.get('signals', []))} signals")
    return result

@test_mode_wrapper
def execute_signal(signal_id):
    """TEST MODE: Process the signal but don't actually send to MT5"""
    # Find the signal
    signal = db.session.query(Signal).filter(Signal.id == signal_id).first()
    
    if not signal:
        logger.error(f"[TEST] Signal with ID {signal_id} not found")
        return jsonify({"status": "error", "message": f"Signal with ID {signal_id} not found", "test_mode": True}), 404
    
    # Log what would happen in production
    logger.info(f"[TEST] Would execute signal {signal_id} for {signal.symbol} ({signal.action})")
    
    # Change the signal status to ACTIVE if it's PENDING
    if signal.status.name == 'PENDING':
        signal.status = SignalStatus.ACTIVE
        db.session.commit()
        logger.info(f"[TEST] Updated signal {signal_id} status to ACTIVE")
    
    # Return success response
    return jsonify({
        "status": "success", 
        "message": "Signal processed in TEST mode (no actual MT5 communication)",
        "signal_id": signal_id,
        "test_mode": True
    })

@test_mode_wrapper
def heartbeat():
    """TEST MODE: Simulate heartbeat response"""
    # Parse request data
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data provided", "test_mode": True}), 400
        
        account_id = data.get('account_id')
        terminal_id = data.get('terminal_id')
        
        if not account_id or not terminal_id:
            return jsonify({"status": "error", "message": "Missing account_id or terminal_id", "test_mode": True}), 400
        
        logger.info(f"[TEST] Received heartbeat from MT5 terminal {terminal_id} for account {account_id}")
        
        # Return success response
        return jsonify({
            "status": "success",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Heartbeat received in TEST mode",
            "test_mode": True
        })
        
    except Exception as e:
        logger.error(f"[TEST] Error processing heartbeat: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "test_mode": True}), 500

# Apply the test wrapper to other functions as needed
# This ensures they log properly but don't actually communicate with MT5
heartbeat = test_mode_wrapper(heartbeat)

# Print confirmation of module initialization
logger.info("MT5 EA API Test wrapper initialized")