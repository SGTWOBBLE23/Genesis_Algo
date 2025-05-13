#!/usr/bin/env python3
"""
Cleanup script to remove duplicate trades from the database.
This script identifies and removes duplicate trades based on ticket numbers.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment or use default
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

def cleanup_duplicate_trades(account_id=None):
    """
    Find and remove duplicate trades for the given account.
    
    Args:
        account_id (str): Optional account ID to limit cleanup to a specific account
                         If not provided, all accounts will be cleaned up
                         
    Returns:
        dict: Summary of cleanup operation
    """
    try:
        # Create database connection
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Build the account filter
        account_filter = f"WHERE account_id = '{account_id}'" if account_id else ""
        
        # Find duplicates (keep the lowest ID for each ticket)
        logger.info(f"Finding duplicate trades{' for account ' + account_id if account_id else ''}...")
        
        # This query identifies all duplicate ticket rows except the one with the lowest ID
        query = text(f"""
            WITH duplicates AS (
                SELECT id, ticket, account_id,
                       ROW_NUMBER() OVER (PARTITION BY ticket, account_id ORDER BY id) as row_num
                FROM trades
                {account_filter}
            )
            SELECT id FROM duplicates WHERE row_num > 1
        """)
        
        result = session.execute(query)
        duplicate_ids = [row[0] for row in result]
        
        if not duplicate_ids:
            logger.info("No duplicate trades found")
            session.close()
            return {"success": True, "removed": 0, "message": "No duplicates found"}
        
        logger.info(f"Found {len(duplicate_ids)} duplicate trades")
        
        # Delete the duplicates
        if duplicate_ids:
            delete_query = text(f"""
                DELETE FROM trades 
                WHERE id IN ({','.join(str(id) for id in duplicate_ids)})
            """)
            
            session.execute(delete_query)
            session.commit()
            logger.info(f"Successfully removed {len(duplicate_ids)} duplicate trades")
        
        session.close()
        
        return {
            "success": True, 
            "removed": len(duplicate_ids),
            "message": f"Successfully removed {len(duplicate_ids)} duplicate trades"
        }
    
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return {"success": False, "error": str(e)}
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up duplicate trades in the database")
    parser.add_argument("--account", help="Account ID (optional, will clean all accounts if not specified)")
    
    args = parser.parse_args()
    
    result = cleanup_duplicate_trades(args.account)
    
    if result.get("success"):
        logger.info(result["message"])
        sys.exit(0)
    else:
        logger.error(f"Cleanup failed: {result.get('error')}")
        sys.exit(1)