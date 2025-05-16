#!/usr/bin/env python3
"""
Fix Open Trades Utility

This script helps correct the discrepancy between actual open trades in MT5 
and what's shown in the database. It will:
1. Mark all trades as CLOSED where status is OPEN but they are not in the list of actual open trades
2. Display a summary of changes made
"""

import os
import sys
from datetime import datetime, timezone

# Import the required modules from app.py where the models are defined
from app import db, app, Trade, TradeStatus

def get_actual_open_trades():
    """
    Gather the list of actually open trades from MT5 reports
    
    Returns:
        list: List of open trade tickets
    """
    try:
        # Ask the user to provide the currently open ticket numbers
        print("\nPlease enter the ticket numbers for your 4 open trades, separated by commas:")
        print("For example: 128350911,128356817,128350903,128353842")
        user_input = input("> ").strip()
        actual_open_tickets = []
        
        if user_input:
            user_tickets = [ticket.strip() for ticket in user_input.split(",")]
            actual_open_tickets.extend(user_tickets)
            
        return actual_open_tickets
    except Exception as e:
        print(f"Error gathering open trades: {e}")
        return []

def fix_open_trades(actual_tickets):
    """
    Update the database to match actual open trades
    
    Args:
        actual_tickets (list): List of tickets that are actually open
    """
    try:
        # Get all trades marked as OPEN in the database
        with app.app_context():
            db_open_trades = Trade.query.filter_by(status=TradeStatus.OPEN).all()
            print(f"Found {len(db_open_trades)} trades marked as OPEN in the database")
            
            # Count trades to update
            to_update = []
            for trade in db_open_trades:
                if trade.ticket not in actual_tickets:
                    to_update.append(trade)
            
            print(f"Found {len(to_update)} trades that need to be marked as CLOSED")
            
            # Confirm with user
            if len(to_update) > 0:
                print("\nHere are the first 10 trades that will be updated:")
                for i, trade in enumerate(to_update[:10]):
                    print(f"{i+1}. Ticket: {trade.ticket}, Symbol: {trade.symbol}")
                
                print(f"\nTotal trades to update: {len(to_update)}")
                confirm = input("Do you want to proceed with updating these trades? (y/n): ")
                
                if confirm.lower() == 'y':
                    # Update trades in batches to avoid timeouts
                    batch_size = 50
                    total_updated = 0
                    
                    for i in range(0, len(to_update), batch_size):
                        batch = to_update[i:i+batch_size]
                        for trade in batch:
                            trade.status = TradeStatus.CLOSED
                            trade.closed_at = datetime.now(timezone.utc)
                            if trade.pnl is None:
                                trade.pnl = 0.0  # Set a default PNL if none exists
                        
                        db.session.commit()
                        total_updated += len(batch)
                        print(f"Updated {total_updated}/{len(to_update)} trades...")
                    
                    print(f"\nSuccessfully updated {total_updated} trades!")
                    
                    # Verify the changes
                    remaining_open = Trade.query.filter_by(status=TradeStatus.OPEN).count()
                    print(f"Remaining open trades in database: {remaining_open}")
                else:
                    print("Operation cancelled by user.")
            else:
                print("No trades need to be updated.")
                
    except Exception as e:
        print(f"Error fixing open trades: {e}")
        db.session.rollback()

if __name__ == "__main__":
    print("=" * 50)
    print("OPEN TRADES FIX UTILITY")
    print("=" * 50)
    print("This utility will fix discrepancies between actual open trades in MT5")
    print("and what's shown in the database.")
    print("\nGathering actual open trades...")
    
    actual_open_tickets = get_actual_open_trades()
    if actual_open_tickets:
        print(f"Found {len(actual_open_tickets)} actual open trades: {', '.join(actual_open_tickets)}")
        fix_open_trades(actual_open_tickets)
    else:
        print("Could not determine actual open trades. No changes made.")
    
    print("\nOperation complete.")