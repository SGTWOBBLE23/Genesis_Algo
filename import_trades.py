import os
import pandas as pd
from datetime import datetime
from app import db, Trade, TradeStatus, TradeSide
from trade_logger import TradeLogger

def import_trades_from_excel(file_path, account_id=None):
    """
    Import trades from an MT5 report Excel file.
    
    Args:
        file_path: Path to the Excel file
        account_id: Account identifier (optional)
    
    Returns:
        dict: Summary of imported trades
    """
    # Initialize trade logger
    trade_logger = TradeLogger()
    
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
    
    # Process each row
    for index, row in df.iterrows():
        try:
            # Map Excel columns to trade fields
            # This mapping needs adjustment based on your Excel columns
            trade_data = {
                "ticket": str(row.get("Ticket") or row.get("Order") or ""),
                "symbol": row.get("Symbol", ""),
                "side": "BUY" if row.get("Type", "").upper() in ["BUY", "BUY LIMIT", "BUY STOP"] else "SELL",
                "lot": row.get("Volume", 0.0),
                "entry": row.get("Price", 0.0),
                "exit": row.get("Price.1", 0.0),  # Adjust column name as needed
                "sl": row.get("S / L", 0.0),
                "tp": row.get("T / P", 0.0),
                "pnl": row.get("Profit", 0.0),
                "status": "CLOSED" if row.get("Profit", None) is not None else "OPEN",
                "account_id": account_id or "MT5_ACCOUNT"
            }
            
            # Process dates
            for date_field in ["Time", "Open Time", "Close Time"]:
                if date_field in row and row[date_field]:
                    date_str = row[date_field]
                    if isinstance(date_str, str):
                        try:
                            # Try different date formats
                            for fmt in ["%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    if date_field in ["Time", "Open Time"]:
                                        trade_data["opened_at"] = date_obj
                                    elif date_field == "Close Time":
                                        trade_data["closed_at"] = date_obj
                                    break
                                except ValueError:
                                    continue
                        except Exception as e:
                            print(f"Error parsing date {date_str}: {e}")
                    elif isinstance(date_str, datetime):
                        if date_field in ["Time", "Open Time"]:
                            trade_data["opened_at"] = date_str
                        elif date_field == "Close Time":
                            trade_data["closed_at"] = date_str
            
            # Check if trade already exists in database
            existing_trade = db.session.query(Trade).filter_by(ticket=trade_data["ticket"]).first()
            
            if existing_trade:
                # Update existing trade
                for key, value in trade_data.items():
                    if hasattr(existing_trade, key) and value is not None:
                        setattr(existing_trade, key, value)
                        
                # Handle enums
                if trade_data["side"]:
                    existing_trade.side = TradeSide(trade_data["side"])
                if trade_data["status"]:
                    existing_trade.status = TradeStatus(trade_data["status"])
                    
                db.session.commit()
                results["updated"] += 1
            else:
                # Create a new trade
                new_trade = Trade(
                    ticket=trade_data["ticket"],
                    symbol=trade_data["symbol"],
                    side=trade_data["side"],
                    lot=trade_data["lot"],
                    entry=trade_data["entry"],
                    exit=trade_data["exit"],
                    sl=trade_data["sl"],
                    tp=trade_data["tp"],
                    pnl=trade_data["pnl"],
                    status=trade_data["status"],
                    account_id=trade_data["account_id"],
                    opened_at=trade_data.get("opened_at"),
                    closed_at=trade_data.get("closed_at"),
                )
                db.session.add(new_trade)
                db.session.commit()
                results["imported"] += 1
                
        except Exception as e:
            results["errors"] += 1
            error_detail = f"Error processing row {index}: {str(e)}"
            results["error_details"].append(error_detail)
            print(error_detail)
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python import_trades.py <excel_file_path> [account_id]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    account_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = import_trades_from_excel(file_path, account_id)
    print(f"Import complete: {results['imported']} imported, {results['updated']} updated, {results['errors']} errors")