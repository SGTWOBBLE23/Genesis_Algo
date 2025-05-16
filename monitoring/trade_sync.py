#!/usr/bin/env python3
"""
Trade Synchronization Monitor

This module automatically synchronizes the database trade status with MT5.
It runs as part of the regular monitoring system to ensure database trades
match what's actually in MT5.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from app import app, db, Trade, TradeStatus
from mt5_ea_api import MetaTrader5API
from monitoring.discord_alerts import send_discord_alert

logger = logging.getLogger(__name__)

# How often to check for trade mismatches (in seconds)
CHECK_INTERVAL = 300  # 5 minutes

# How long to wait between alerts (in seconds)
ALERT_COOLDOWN = 600  # 10 minutes

last_alert_time = None

def get_mt5_active_tickets() -> Set[str]:
    """Get the set of active ticket numbers from MT5"""
    try:
        mt5_api = MetaTrader5API()
        active_trades = mt5_api.get_open_trades()
        
        if active_trades is None or not isinstance(active_trades, list):
            logger.error("Failed to get active trades from MT5")
            return set()
            
        # Extract ticket numbers
        ticket_set = {str(trade.get('ticket', '')) for trade in active_trades 
                     if trade.get('ticket')}
        
        logger.info(f"Found {len(ticket_set)} active trades in MT5")
        return ticket_set
        
    except Exception as e:
        logger.error(f"Error getting MT5 active trades: {e}")
        return set()

def get_db_open_trades() -> List[Trade]:
    """Get all trades marked as OPEN in the database"""
    try:
        with app.app_context():
            open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
            logger.info(f"Found {len(open_trades)} open trades in database")
            return open_trades
    except Exception as e:
        logger.error(f"Error getting database open trades: {e}")
        return []

def synchronize_trades() -> Dict[str, int]:
    """
    Synchronize database trade status with MT5
    
    Returns:
        Dict with counts of trades checked, closed, and errors
    """
    global last_alert_time
    
    stats = {
        "total_checked": 0,
        "closed": 0,
        "errors": 0
    }
    
    # Get active tickets from MT5
    mt5_tickets = get_mt5_active_tickets()
    
    # If we couldn't get MT5 tickets, don't proceed
    if not mt5_tickets:
        stats["errors"] += 1
        return stats
    
    # Get trades marked as OPEN in database
    db_open_trades = get_db_open_trades()
    stats["total_checked"] = len(db_open_trades)
    
    # If trade count matches approximately, no need to sync
    if abs(len(mt5_tickets) - len(db_open_trades)) <= 1:
        logger.info("Trade counts match, no sync needed")
        return stats
        
    # Update database to match MT5 reality
    try:
        with app.app_context():
            closed_tickets = []
            for trade in db_open_trades:
                if trade.ticket not in mt5_tickets:
                    logger.info(f"Trade {trade.ticket} not found in active MT5 trades - marking as CLOSED")
                    
                    # Update trade status to CLOSED
                    trade.status = TradeStatus.CLOSED
                    trade.closed_at = datetime.now()
                    
                    # Update context
                    context = trade.context or {}
                    context["last_update"] = datetime.now().isoformat()
                    context["closed_by"] = "trade_sync_monitor"
                    trade.context = context
                    
                    closed_tickets.append(trade.ticket)
                    stats["closed"] += 1
            
            # Commit the changes
            if closed_tickets:
                db.session.commit()
                logger.info(f"Updated {len(closed_tickets)} trades to CLOSED status")
                logger.info(f"Updated tickets: {closed_tickets}")
                
                # Don't send alerts too frequently
                current_time = time.time()
                if (last_alert_time is None or 
                        current_time - last_alert_time > ALERT_COOLDOWN):
                    send_trade_sync_alert(mt5_tickets, db_open_trades, closed_tickets)
                    last_alert_time = current_time
                
    except Exception as e:
        logger.error(f"Error synchronizing trades: {e}")
        stats["errors"] += 1
        
    # Verify the updates
    with app.app_context():
        remaining_open = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
        logger.info(f"Remaining open trades in database: {remaining_open}")
    
    return stats

def send_trade_sync_alert(
    mt5_tickets: Set[str], 
    db_trades: List[Trade], 
    closed_tickets: List[str]
) -> None:
    """Send a Discord alert about the trade synchronization"""
    try:
        title = "Trade Database Synchronized"
        
        description = (
            f"MT5 shows {len(mt5_tickets)} open positions vs {len(db_trades)} in database.\n"
            f"Automatically closed {len(closed_tickets)} stale trades in database."
        )
        
        fields = [
            {"name": "MT5 Open Tickets", "value": ", ".join(mt5_tickets) or "None", "inline": False},
            {"name": "Closed Stale Tickets", "value": ", ".join(closed_tickets) or "None", "inline": False}
        ]
        
        # Use orange for warnings
        send_discord_alert(title, description, fields, "orange")
        
    except Exception as e:
        logger.error(f"Failed to send trade sync alert: {e}")
        
def check_trade_synchronization():
    """Main function to check and sync trade status"""
    try:
        logger.info("Starting trade synchronization check")
        stats = synchronize_trades()
        logger.info(f"Trade sync completed: {stats}")
    except Exception as e:
        logger.error(f"Error in trade synchronization check: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Running trade synchronization check")
    check_trade_synchronization()