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
    
    # Skip header rows (first 6 rows)
    data_df = df.iloc[6:].reset_index(drop=True)
    data_df.columns = [
        'Time', 'Position', 'Symbol', 'Type', 'Volume', 'Price', 'SL', 'TP',
        'CloseTime', 'ClosePrice', 'Commission', 'Swap', 'Profit', 'Extra'
    ]
    
    # Track results
    results = {
        "total": len(data_df),
        "imported": 0,
        "updated": 0,
        "errors": 0,
        "error_details": []
    }
    
    # Get metadata and trades table
    metadata = MetaData()
    trades_table = Table("trades", metadata, autoload_with=engine)
    
    # Process each row
    for index, row in data_df.iterrows():
        try:
            # Extract position ticket number
            if pd.isna(row["Position"]):
                continue
                
            ticket = str(int(row["Position"]))
            
            # Skip if no ticket number
            if not ticket:
                results["errors"] += 1
                results["error_details"].append(f"Row {index}: Missing ticket number")
                continue
                
            # Map Excel columns to trade fields
            symbol = row["Symbol"]
            trade_type = str(row["Type"]).lower()
            side = "BUY" if "buy" in trade_type else "SELL"
            
            try:
                lot = float(row["Volume"])
            except (ValueError, TypeError):
                results["errors"] += 1
                results["error_details"].append(f"Row {index}: Invalid volume {row['Volume']}")
                continue
                
            try:
                entry_price = float(row["Price"])
            except (ValueError, TypeError):
                results["errors"] += 1
                results["error_details"].append(f"Row {index}: Invalid price {row['Price']}")
                continue
            
            # Exit price
            exit_price = None
            if pd.notna(row["ClosePrice"]):
                try:
                    exit_price = float(row["ClosePrice"])
                except (ValueError, TypeError):
                    pass
            
            # Stop loss and take profit
            sl = None
            if pd.notna(row["SL"]):
                try:
                    sl = float(row["SL"])
                except (ValueError, TypeError):
                    pass
                
            tp = None  
            if pd.notna(row["TP"]):
                try:
                    tp = float(row["TP"])
                except (ValueError, TypeError):
                    pass
            
            # Profit
            pnl = None
            if pd.notna(row["Profit"]):
                try:
                    pnl = float(row["Profit"])
                except (ValueError, TypeError):
                    pass
                
            # Determine status based on profit/exit
            status = "OPEN"
            if exit_price is not None or pnl is not None:
                status = "CLOSED"
            
            # Process dates
            opened_at = None
            if pd.notna(row["Time"]):
                time_str = str(row["Time"])
                try:
                    opened_at = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        opened_at = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                    except ValueError:
                        opened_at = None
            
            # Close time
            closed_at = None
            if pd.notna(row["CloseTime"]):
                time_str = str(row["CloseTime"])
                try:
                    closed_at = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        closed_at = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                    except ValueError:
                        closed_at = None
            
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
                print(f"Updated trade {ticket}")
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
                print(f"Imported trade {ticket}")
                
        except Exception as e:
            results["errors"] += 1
            error_detail = f"Row {index}: {str(e)}"
            results["error_details"].append(error_detail)
            print(error_detail)
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_trades_fixed2.py <excel_file_path> [account_id]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    account_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = import_trades_from_excel(file_path, account_id)
    print(f"Import complete:")
    print(f"- {results['imported']} trades imported")
    print(f"- {results['updated']} trades updated")
    print(f"- {results['errors']} errors")
    
    if results['errors'] > 0 and results['errors'] <= 20:
        print("\nError details:")
        for error in results["error_details"]:
            print(f"- {error}")
    elif results['errors'] > 20:
        print("\nFirst 20 error details:")
        for error in results["error_details"][:20]:
            print(f"- {error}")
        print(f"- ... and {len(results['error_details']) - 20} more errors")