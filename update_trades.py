#!/usr/bin/env python3
"""
Script to update trades in the database to match actual open positions in MT5.
This will:
1. Mark all existing OPEN trades as CLOSED
2. Insert new trades from the provided screenshot as OPEN
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

def update_trades():
    """Update trades to match actual MT5 status"""
    try:
        # Create database session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # First mark all existing OPEN trades as CLOSED
        now = datetime.now()
        update_query = text("""
            UPDATE trades 
            SET status = 'CLOSED', 
                closed_at = :now,
                context_json = json_build_object('reset_by', 'system', 'reset_at', :now_str)
            WHERE status = 'OPEN'
        """)
        
        result = session.execute(update_query, {"now": now, "now_str": now.isoformat()})
        logger.info(f"Reset {result.rowcount} previously OPEN trades to CLOSED")
        
        # Now insert the actual open trades from the screenshot
        open_trades = [
            {"ticket": "121662348", "symbol": "EURUSD", "side": "BUY", "lot": 0.01, "entry": 1.11845},
            {"ticket": "121662349", "symbol": "EURUSD", "side": "BUY", "lot": 0.01, "entry": 1.11828},
            {"ticket": "127945288", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.741},
            {"ticket": "127945289", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.733},
            {"ticket": "127945290", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.538},
            {"ticket": "127945291", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.538},
            {"ticket": "127945292", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.755},
            {"ticket": "127945293", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.666},
            {"ticket": "127945294", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.666},
            {"ticket": "127945295", "symbol": "GBPJPY", "side": "SELL", "lot": 0.01, "entry": 193.666},
            {"ticket": "127946274", "symbol": "XAUUSD", "side": "BUY", "lot": 0.01, "entry": 3234.75},
            {"ticket": "127993461", "symbol": "XAUUSD", "side": "SELL", "lot": 0.02, "entry": 3224.76},
            {"ticket": "127993462", "symbol": "XAUUSD", "side": "SELL", "lot": 0.01, "entry": 3223.62},
            {"ticket": "127999923", "symbol": "XAUUSD", "side": "BUY", "lot": 0.01, "entry": 3224.75},
            {"ticket": "128122159", "symbol": "XAUUSD", "side": "SELL", "lot": 0.01, "entry": 3234.76}
        ]
        
        account_id = "163499"  # From your screenshot/previous import
        opened_at = datetime.now()
        
        for trade in open_trades:
            trade_data = {
                "account_id": account_id,
                "ticket": trade["ticket"],
                "symbol": trade["symbol"],
                "side": trade["side"],
                "lot": trade["lot"],
                "entry": trade["entry"],
                "status": "OPEN",
                "opened_at": opened_at,
                "context_json": f'{{"last_update": "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"}}'
            }
            
            # Check if this trade already exists
            check_query = text("SELECT id FROM trades WHERE ticket = :ticket")
            existing = session.execute(check_query, {"ticket": trade["ticket"]}).fetchone()
            
            if existing:
                # Update existing trade
                update_query = text("""
                    UPDATE trades 
                    SET status = 'OPEN',
                        closed_at = NULL,
                        context_json = :context_json
                    WHERE ticket = :ticket
                """)
                session.execute(update_query, {"ticket": trade["ticket"], "context_json": trade_data["context_json"]})
                logger.info(f"Updated existing trade with ticket {trade['ticket']} to OPEN")
            else:
                # Insert new trade
                columns = ", ".join(trade_data.keys())
                values = ", ".join(f":{key}" for key in trade_data.keys())
                insert_query = text(f"INSERT INTO trades ({columns}) VALUES ({values})")
                session.execute(insert_query, trade_data)
                logger.info(f"Inserted new trade with ticket {trade['ticket']}")
        
        # Commit all changes
        session.commit()
        logger.info("Successfully updated trade database to match MT5")
        
        return {
            "success": True,
            "closed_count": result.rowcount,
            "open_count": len(open_trades)
        }
    
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    result = update_trades()
    if "error" in result:
        logger.error(f"Update failed: {result['error']}")
        sys.exit(1)
    else:
        logger.info(f"Update completed successfully.")
        logger.info(f"Set {result['closed_count']} trades to CLOSED")
        logger.info(f"Created/updated {result['open_count']} trades as OPEN")