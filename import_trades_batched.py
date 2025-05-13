#!/usr/bin/env python3
"""
Improved MT5 Excel trade report importer with batch processing and duplicate detection.
This script imports trades from MT5 Excel report files into the Genesis database.

Features:
- Processes trades in batches to avoid timeouts
- Skips trades that already exist in the database
- Tracks and reports import progress
- Handles reconnecting to database between batches
"""

import os
import sys
import time
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment or use default
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

def create_db_session():
    """Create a fresh database session"""
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        return Session()
    except SQLAlchemyError as e:
        logger.error(f"Database connection error: {e}")
        return None

def get_existing_tickets(session, account_id):
    """Get set of ticket numbers already in the database for this account"""
    try:
        result = session.execute(text("SELECT ticket FROM trades WHERE account_id = :account_id"), 
                                 {"account_id": account_id})
        return {str(row[0]) for row in result}
    except SQLAlchemyError as e:
        logger.error(f"Error getting existing tickets: {e}")
        return set()

def parse_mt5_datetime(date_str):
    """Parse MT5 report date format to Python datetime"""
    if not date_str or pd.isna(date_str):
        return None
    try:
        return datetime.strptime(str(date_str), '%Y.%m.%d %H:%M:%S.%f')
    except ValueError:
        try:
            return datetime.strptime(str(date_str), '%Y.%m.%d %H:%M:%S')
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None

def import_trades_from_excel(file_path, account_id=None, batch_size=25):
    """
    Import trades from an MT5 report Excel file in batches, skipping existing trades.
    
    Args:
        file_path: Path to the Excel file
        account_id: Account identifier (optional)
        batch_size: Number of trades to process in each batch
    
    Returns:
        dict: Summary of imported trades
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    try:
        # Read the Excel file
        logger.info(f"Reading Excel file: {file_path}")
        df = pd.read_excel(file_path)
        
        # Get account ID from file name if not provided
        if not account_id:
            # Try to extract from filename (assumes format like ReportHistory-123456.xlsx)
            try:
                filename = os.path.basename(file_path)
                account_id = filename.split('-')[1].split('.')[0]
                logger.info(f"Extracted account ID from filename: {account_id}")
            except:
                logger.error("Could not extract account ID from filename. Please provide it explicitly.")
                return {"error": "Account ID not provided and could not be extracted from filename"}
        
        # Skip header rows
        if df.shape[0] > 6:  # Make sure we have enough rows
            data_df = df.iloc[6:]  # Skip first 6 rows (header)
        else:
            return {"error": "Excel file has insufficient rows"}
        
        # Keep only rows with ticket numbers
        non_null_positions = data_df[pd.notna(data_df.iloc[:,1])]
        
        # Get total number of trades
        total_trades = len(non_null_positions)
        if total_trades == 0:
            return {"error": "No valid trades found in the Excel file"}
        
        logger.info(f"Found {total_trades} trades in the Excel file")
        
        # Create initial database session and get existing tickets
        session = create_db_session()
        if not session:
            return {"error": "Could not connect to database"}
        
        existing_tickets = get_existing_tickets(session, account_id)
        logger.info(f"Found {len(existing_tickets)} existing trades in the database for account {account_id}")
        
        # Initialize counters
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_trades, batch_size):
            # Create a fresh database session for each batch
            if i > 0:
                session.close()
                session = create_db_session()
                if not session:
                    logger.error("Database connection lost. Stopping import.")
                    break
            
            batch = non_null_positions.iloc[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(total_trades+batch_size-1)//batch_size} ({len(batch)} trades)")
            
            for _, row in batch.iterrows():
                try:
                    ticket = str(row[1])
                    if ticket in existing_tickets:
                        skipped_count += 1
                        continue
                    
                    # Parse trade data
                    trade_type = str(row[3]).lower()
                    side = "BUY" if trade_type == "buy" else "SELL"
                    
                    # Extract values from Excel
                    symbol = str(row[2])
                    
                    # Safer parsing with better error handling
                    try:
                        # Handle volume with format like "0.1 / 0" by taking the first part
                        volume_str = str(row[4]) if pd.notna(row[4]) else "0.0"
                        # Skip non-numeric values like 'canceled', 'filled', etc.
                        if any(x in volume_str.lower() for x in ['cancel', 'fill', 'market', 'volume', 'order']):
                            raise ValueError(f"Non-trade entry found: {volume_str}")
                            
                        if "/" in volume_str:
                            volume_str = volume_str.split("/")[0].strip()
                        volume = float(volume_str)
                        
                        # Parse prices safely
                        entry_price = float(row[5]) if pd.notna(row[5]) and isinstance(row[5], (int, float, str)) and str(row[5]).replace('.', '', 1).isdigit() else None
                        sl_price = float(row[6]) if pd.notna(row[6]) and isinstance(row[6], (int, float, str)) and str(row[6]).replace('.', '', 1).isdigit() else None
                        tp_price = float(row[7]) if pd.notna(row[7]) and isinstance(row[7], (int, float, str)) and str(row[7]).replace('.', '', 1).isdigit() else None
                        
                        close_time = parse_mt5_datetime(row[8])
                        
                        exit_price = float(row[9]) if pd.notna(row[9]) and isinstance(row[9], (int, float, str)) and str(row[9]).replace('.', '', 1).isdigit() else None
                        pnl = float(row[12]) if pd.notna(row[12]) and isinstance(row[12], (int, float, str)) and str(row[12]).replace('.', '', 1).isdigit() else None
                        open_time = parse_mt5_datetime(row[13]) if len(row) > 13 else None
                    except ValueError as e:
                        # Re-raise to be caught by the outer exception handler
                        raise ValueError(str(e))
                    
                    # Determine trade status
                    status = "CLOSED" if close_time else "OPEN"
                    
                    # Prepare trade data for insertion
                    trade_data = {
                        "account_id": account_id,
                        "ticket": ticket,
                        "symbol": symbol,
                        "side": side, 
                        "lot": volume,
                        "entry": entry_price,
                        "exit": exit_price,
                        "sl": sl_price,
                        "tp": tp_price,
                        "pnl": pnl,
                        "status": status,
                        "opened_at": open_time,
                        "closed_at": close_time,
                        "context_json": f'{{"last_update": "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"}}'
                    }
                    
                    # Build insert query
                    columns = ", ".join(trade_data.keys())
                    values = ", ".join(f":{key}" for key in trade_data.keys())
                    query = text(f"INSERT INTO trades ({columns}) VALUES ({values})")
                    
                    # Execute query
                    session.execute(query, trade_data)
                    imported_count += 1
                    
                    # Add to existing tickets set to avoid duplicates within the same import
                    existing_tickets.add(ticket)
                    
                except Exception as e:
                    logger.error(f"Error importing trade {row[1]}: {e}")
                    error_count += 1
            
            # Commit batch
            try:
                session.commit()
                logger.info(f"Committed batch. Progress: {i+len(batch)}/{total_trades} trades processed")
            except SQLAlchemyError as e:
                logger.error(f"Error committing batch: {e}")
                session.rollback()
            
            # Short pause between batches to avoid overloading the database
            time.sleep(0.5)
        
        # Close final session if it exists
        if session:
            session.close()
        
        return {
            "success": True,
            "account_id": account_id,
            "total_trades": total_trades,
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": error_count
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import MT5 trades from Excel report")
    parser.add_argument("file", help="Path to Excel report file")
    parser.add_argument("--account", help="Account ID (optional, will try to extract from filename)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size for processing trades")
    
    args = parser.parse_args()
    
    result = import_trades_from_excel(args.file, args.account, args.batch_size)
    
    if "error" in result:
        logger.error(f"Import failed: {result['error']}")
        sys.exit(1)
    else:
        logger.info("Import summary:")
        logger.info(f"Account: {result['account_id']}")
        logger.info(f"Total trades in file: {result['total_trades']}")
        logger.info(f"Trades imported: {result['imported']}")
        logger.info(f"Trades skipped (already exist): {result['skipped']}")
        logger.info(f"Import errors: {result['errors']}")
        logger.info("Import completed successfully")