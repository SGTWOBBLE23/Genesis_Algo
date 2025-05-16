#!/usr/bin/env python3
"""
Add missing active trades to the database
This will create trade records for the active trades that exist in MT5 but not in the database
"""
import sys
import logging
from datetime import datetime
from app import app, db, Trade, TradeStatus, TradeSide

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enter your actual open trade details from MT5
ACTIVE_MT5_TRADES = [
    # Ticket, Symbol, Side, Lot Size, Open Price
    ("128402155", "XAUUSD", TradeSide.BUY, 0.1, 3213.45),
    ("128350776", "XAUUSD", TradeSide.BUY, 0.1, 3209.53),
    ("128391710", "XAUUSD", TradeSide.BUY, 0.1, 3212.70),
    ("128407156", "EURUSD", TradeSide.BUY, 0.1, 1.1200), 
    ("128407216", "EURUSD", TradeSide.BUY, 0.1, 1.1205),
    ("128472632", "XAUUSD", TradeSide.BUY, 0.1, 3214.80)
]

def add_missing_trades():
    """Add the active MT5 trades to the database"""
    with app.app_context():
        try:
            added_trades = []
            
            for ticket, symbol, side, lot, entry in ACTIVE_MT5_TRADES:
                # Check if trade already exists
                existing = db.session.query(Trade).filter_by(ticket=ticket).first()
                
                if existing:
                    logger.info(f"Trade {ticket} already exists in database")
                    continue
                    
                # Create new trade
                logger.info(f"Adding trade {ticket} to database")
                new_trade = Trade(
                    ticket=ticket,
                    symbol=symbol,
                    side=side,
                    lot=lot,
                    entry=entry,
                    status=TradeStatus.OPEN,
                    opened_at=datetime.now(),  # Actual open time not available
                    account_id="163499"  # Your MT5 account ID
                )
                
                # Add context
                context = {
                    "added_by": "manual_script",
                    "added_at": datetime.now().isoformat()
                }
                new_trade.context = context
                
                db.session.add(new_trade)
                added_trades.append(ticket)
            
            # Commit the changes
            if added_trades:
                db.session.commit()
                logger.info(f"Added {len(added_trades)} trades to database")
                logger.info(f"Added tickets: {added_trades}")
            else:
                logger.info("No trades needed to be added")
                
            # Verify the updates
            open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
            logger.info(f"Open trades in database: {open_trades}")
            
            return len(added_trades)
            
        except Exception as e:
            logger.error(f"Error adding trades: {e}")
            db.session.rollback()
            return 0

if __name__ == "__main__":
    logger.info("Running add missing trades script")
    added = add_missing_trades()
    logger.info(f"Add missing trades complete. Added {added} trades.")
    
    if added > 0:
        logger.info("Trades added successfully to database")
    else:
        logger.info("No trades were added or there was an error")