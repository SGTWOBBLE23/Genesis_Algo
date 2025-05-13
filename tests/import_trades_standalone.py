import os
import sys
import pandas as pd
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum, Text, MetaData, Table, select, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Get database URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable not set")
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)
session = Session(engine)

def import_trades_from_excel(file_path, account_id=None):
    """
    Import trades from an MT5 report Excel file.
    
    Args:
        file_path: Path to the Excel file
        account_id: Account identifier (optional)
    
    Returns:
        dict: Summary of imported trades
    """
    # Read Excel file
    df = pd.read_excel(file_path)
    
    # For debugging
    print(f"Found {len(df)} rows in Excel file")
    print(f"Columns: {df.columns.tolist()}")
    
    # Track results
    results = {
        "total": len(df),
        "imported": 0,
        "updated": 0,
        "errors": 0,
        "error_details": []
    }
    
    # Get metadata and trades table
    metadata = MetaData()
    trades_table = Table("trades", metadata, autoload_with=engine)
    
    # Process each row
    for index, row in df.iterrows():
        try:
            # Extract values from Excel with fallbacks
            ticket = str(row.get("Ticket", "") or row.get("Order", "") or "")
            symbol = row.get("Symbol", "")
            trade_type = row.get("Type", "").upper()
            side = "BUY" if trade_type in ["BUY", "BUY LIMIT", "BUY STOP"] else "SELL"
            lot = float(row.get("Volume", 0) or 0)
            
            # Handle various price column names
            entry_price = None
            for price_col in ["Price", "Open", "Open Price"]:
                if price_col in row and pd.notna(row[price_col]):
                    entry_price = float(row[price_col])
                    break
            
            exit_price = None
            for exit_col in ["Price.1", "Close", "Close Price"]:
                if exit_col in row and pd.notna(row[exit_col]):
                    exit_price = float(row[exit_col])
                    break
            
            # Stop loss and take profit
            sl = float(row.get("S / L", 0) or 0) if "S / L" in row else None
            tp = float(row.get("T / P", 0) or 0) if "T / P" in row else None
            
            # Profit and status
            pnl = float(row.get("Profit", 0) or 0) if "Profit" in row else None
            status = "CLOSED" if pd.notna(row.get("Profit", None)) and exit_price else "OPEN"
            
            # Process dates
            opened_at = None
            closed_at = None
            
            # Check common date column names
            for open_date_col in ["Time", "Open Time"]:
                if open_date_col in row and pd.notna(row[open_date_col]):
                    date_val = row[open_date_col]
                    if isinstance(date_val, datetime):
                        opened_at = date_val
                    elif isinstance(date_val, str):
                        # Try various date formats
                        for fmt in ["%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                            try:
                                opened_at = datetime.strptime(date_val, fmt)
                                break
                            except ValueError:
                                continue
                    break
            
            for close_date_col in ["Close Time"]:
                if close_date_col in row and pd.notna(row[close_date_col]):
                    date_val = row[close_date_col]
                    if isinstance(date_val, datetime):
                        closed_at = date_val
                    elif isinstance(date_val, str):
                        # Try various date formats
                        for fmt in ["%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                            try:
                                closed_at = datetime.strptime(date_val, fmt)
                                break
                            except ValueError:
                                continue
                    break
            
            # Skip if no ticket number (essential for identification)
            if not ticket:
                results["errors"] += 1
                results["error_details"].append(f"Row {index}: Missing ticket number")
                continue
            
            # Check if trade already exists
            stmt = select(trades_table).where(trades_table.c.ticket == ticket)
            existing_trade = session.execute(stmt).first()
            
            if existing_trade:
                # Update existing trade
                update_values = {
                    "symbol": symbol,
                    "side": side,
                    "lot": lot,
                    "entry": entry_price,
                    "status": status
                }
                
                # Only update non-None values
                if exit_price is not None:
                    update_values["exit"] = exit_price
                if sl is not None:
                    update_values["sl"] = sl
                if tp is not None:
                    update_values["tp"] = tp
                if pnl is not None:
                    update_values["pnl"] = pnl
                if opened_at is not None:
                    update_values["opened_at"] = opened_at
                if closed_at is not None:
                    update_values["closed_at"] = closed_at
                if account_id:
                    update_values["account_id"] = account_id
                
                session.execute(
                    trades_table.update().where(trades_table.c.ticket == ticket).values(**update_values)
                )
                session.commit()
                results["updated"] += 1
            else:
                # Insert new trade
                insert_values = {
                    "ticket": ticket,
                    "symbol": symbol,
                    "side": side,
                    "lot": lot,
                    "entry": entry_price,
                    "status": status,
                    "account_id": account_id or "MT5_ACCOUNT"
                }
                
                # Only include non-None values
                if exit_price is not None:
                    insert_values["exit"] = exit_price
                if sl is not None:
                    insert_values["sl"] = sl
                if tp is not None:
                    insert_values["tp"] = tp
                if pnl is not None:
                    insert_values["pnl"] = pnl
                if opened_at is not None:
                    insert_values["opened_at"] = opened_at
                if closed_at is not None:
                    insert_values["closed_at"] = closed_at
                
                session.execute(trades_table.insert().values(**insert_values))
                session.commit()
                results["imported"] += 1
                
        except Exception as e:
            results["errors"] += 1
            error_detail = f"Error processing row {index}: {str(e)}"
            results["error_details"].append(error_detail)
            print(error_detail)
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_trades_standalone.py <excel_file_path> [account_id]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    account_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = import_trades_from_excel(file_path, account_id)
    print(f"Import complete:")
    print(f"- {results['imported']} trades imported")
    print(f"- {results['updated']} trades updated")
    print(f"- {results['errors']} errors")
    
    if results['errors'] > 0:
        print("\nError details:")
        for error in results["error_details"]:
            print(f"- {error}")