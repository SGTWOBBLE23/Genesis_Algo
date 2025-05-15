#!/usr/bin/env python3
"""
Script to reset all OPEN trades to CLOSED status,
allowing new signals to be processed by risk guard.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

def reset_trades():
    """Reset all OPEN trades to CLOSED status"""
    try:
        # Create database session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Get count of open trades
        count_result = session.execute(text("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'"))
        open_count = count_result.scalar()
        logger.info(f"Found {open_count} OPEN trades")
        
        if open_count == 0:
            logger.info("No OPEN trades to reset")
            return {"success": True, "count": 0}
        
        # Update all open trades to closed
        now = datetime.now()
        update_query = text("""
            UPDATE trades 
            SET status = 'CLOSED', 
                closed_at = :now,
                context_json = json_build_object('reset_by', 'system', 'reset_at', :now_str)
            WHERE status = 'OPEN'
        """)
        
        result = session.execute(update_query, {"now": now, "now_str": now.isoformat()})
        session.commit()
        
        logger.info(f"Reset {result.rowcount} trades from OPEN to CLOSED")
        
        return {
            "success": True,
            "count": result.rowcount
        }
    
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    result = reset_trades()
    if "error" in result:
        logger.error(f"Reset failed: {result['error']}")
        sys.exit(1)
    else:
        logger.info(f"Reset completed successfully. {result['count']} trades updated.")