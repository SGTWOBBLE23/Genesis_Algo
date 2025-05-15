#!/usr/bin/env python3
"""
Test script to manually add a trade ticket to the close queue
"""
import requests
import sys
import logging
from app import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_ticket_to_close_queue(account_id, ticket):
    """Add a ticket to the close queue via API call"""
    with app.test_client() as client:
        response = client.post('/mt5/close_ticket', 
                               json={"account_id": account_id, "ticket": ticket})
        
        status_code = response.status_code
        data = response.get_json()
        
        logger.info(f"API response: {status_code} - {data}")
        
        # Verify it was added to the queue
        from mt5_ea_api import pending_closures
        logger.info(f"Current pending_closures: {pending_closures}")
        
        return status_code, data

if __name__ == "__main__":
    # Default test values
    account_id = "163499"  # The account ID used in MT5_ReportBot
    ticket = "127405639"   # A ticket from one of the open trades
    
    # Override with command-line arguments if provided
    if len(sys.argv) > 1:
        account_id = sys.argv[1]
    if len(sys.argv) > 2:
        ticket = sys.argv[2]
    
    logger.info(f"Adding ticket {ticket} for account {account_id} to close queue")
    status, result = add_ticket_to_close_queue(account_id, ticket)
    
    if status == 200:
        logger.info("Success! Check MT5 to see if it processes the close request")
    else:
        logger.error(f"Failed to add ticket to close queue: {result}")