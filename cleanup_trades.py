#!/usr/bin/env python3
"""
Cleanup Open Trades Script

This script will clean up the database by:
1. Marking all trades as CLOSED except for the currently open ones 
2. Ensuring all closed trades have a closed_at date and pnl value
"""

import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

# Create the SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Hardcoded ticket numbers from the screenshot (your actual open trades)
# Update these with your own ticket numbers if needed
OPEN_TICKET_NUMBERS = [
    '128350903',  # XAU/USD
    '128350911',  # GBP/JPY
    '128356817',  # USD/JPY
]

def cleanup_open_trades():
    """Mark all trades as CLOSED except for the ones that are actually open"""
    try:
        # Count all trades currently marked as OPEN
        open_count_query = text("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        open_count = session.execute(open_count_query).scalar()
        logger.info(f"Found {open_count} trades currently marked as OPEN in the database")
        
        # Prepare the placeholders for the SQL query
        placeholders = ', '.join([f"'{ticket}'" for ticket in OPEN_TICKET_NUMBERS])
        
        # Update all trades except the actually open ones
        update_query = text(f"""
            UPDATE trades 
            SET status = 'CLOSED',
                closed_at = COALESCE(closed_at, NOW()),
                pnl = COALESCE(pnl, 0.0)
            WHERE status = 'OPEN' AND ticket NOT IN ({placeholders})
        """)
        
        result = session.execute(update_query)
        session.commit()
        
        logger.info(f"Updated {result.rowcount} trades from OPEN to CLOSED")
        
        # Verify remaining open trades
        remaining_query = text("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        remaining_count = session.execute(remaining_query).scalar()
        logger.info(f"Remaining open trades in database: {remaining_count}")
        
        # Show the remaining open trades
        open_trades_query = text("""
            SELECT ticket, symbol, lot, entry, opened_at
            FROM trades
            WHERE status = 'OPEN'
            ORDER BY opened_at DESC
        """)
        open_trades = session.execute(open_trades_query).fetchall()
        
        logger.info("Current open trades in database:")
        for trade in open_trades:
            logger.info(f"Ticket: {trade.ticket}, Symbol: {trade.symbol}, Lot: {trade.lot}, Entry: {trade.entry}")
        
    except Exception as e:
        logger.error(f"Error cleaning up open trades: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("Starting open trades cleanup process...")
    cleanup_open_trades()
    logger.info("Cleanup process completed successfully")