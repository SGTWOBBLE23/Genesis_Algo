#!/usr/bin/env python3
"""
Cleanup script to synchronize database trade status with MT5
This will mark as CLOSED any trades that aren't in your active MT5 trades list
"""
import sys
import logging
from datetime import datetime
from app import app, db, Trade, TradeStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enter your actual open trade ticket numbers from MT5
ACTIVE_MT5_TICKETS = [
    "128402155",  # Replace with your actual open ticket numbers
    "128350776",  # from the MT5 platform
    "128391710",
    "128407156", 
    "128407216",
    "128472632"
]

def cleanup_trades():
    """Mark trades as CLOSED if they're not in the MT5 active trades list"""
    with app.app_context():
        try:
            # Get all trades marked as OPEN in the database
            open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
            logger.info(f"Found {len(open_trades)} trades marked as OPEN in database")
            
            # Track which trades were updated
            updated_trades = []
            
            # Check each open trade against the active tickets list
            for trade in open_trades:
                if trade.ticket not in ACTIVE_MT5_TICKETS:
                    logger.info(f"Trade {trade.ticket} not found in active MT5 trades - marking as CLOSED")
                    
                    # Update trade status to CLOSED
                    trade.status = TradeStatus.CLOSED
                    trade.closed_at = datetime.now()
                    
                    # Update context
                    context = trade.context or {}
                    context["last_update"] = datetime.now().isoformat()
                    context["closed_by"] = "cleanup_script"
                    trade.context = context
                    
                    updated_trades.append(trade.ticket)
            
            # Commit the changes
            if updated_trades:
                db.session.commit()
                logger.info(f"Updated {len(updated_trades)} trades to CLOSED status")
                logger.info(f"Updated tickets: {updated_trades}")
            else:
                logger.info("No trades needed updates")
                
            # Verify the updates
            remaining_open = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
            logger.info(f"Remaining open trades in database: {remaining_open}")
            
            return len(updated_trades)
            
        except Exception as e:
            logger.error(f"Error cleaning up trades: {e}")
            db.session.rollback()
            return 0

if __name__ == "__main__":
    logger.info("Running trade cleanup script")
    updated = cleanup_trades()
    logger.info(f"Cleanup complete. Updated {updated} trades.")
    
    if updated > 0:
        logger.info("Trades synchronized successfully with MT5")
    else:
        logger.info("No trades were updated or there was an error")