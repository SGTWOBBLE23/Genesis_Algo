#!/usr/bin/env python3
"""
Check MT5 trades against database records
Detects discrepancies between MT5 open trades and database records
"""
import os
import json
import logging
import datetime
from app import app, db, Trade, TradeStatus, Settings
from discord_monitor import send_discord_alert

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_mt5_trade_info():
    """
    Get information about open trades from MT5 via settings table
    """
    # This uses existing settings data that is updated by MT5 heartbeats
    mt5_trades = {
        'count': Settings.get_value('mt5_account', 'open_positions', 0),
        'last_update': Settings.get_value('mt5_account', 'last_update', None),
        'balance': Settings.get_value('mt5_account', 'balance', 0.0),
        'equity': Settings.get_value('mt5_account', 'equity', 0.0),
    }
    
    return mt5_trades

def get_database_trade_info():
    """
    Get information about open trades from the database
    """
    open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
    
    trade_info = {
        'count': len(open_trades),
        'symbols': {},
        'total_lot': 0.0,
    }
    
    # Collect statistics about open trades
    for trade in open_trades:
        symbol = trade.symbol
        if symbol not in trade_info['symbols']:
            trade_info['symbols'][symbol] = 0
        
        trade_info['symbols'][symbol] += 1
        trade_info['total_lot'] += trade.lot
    
    return trade_info, open_trades

def check_trade_discrepancies():
    """
    Check for discrepancies between MT5 open trades and database records
    Returns detailed information for alerts
    """
    with app.app_context():
        try:
            # Get trade information from both sources
            mt5_info = get_mt5_trade_info()
            db_info, open_trades = get_database_trade_info()
            
            # Handle type conversion for count comparison
            mt5_count = int(mt5_info['count']) if isinstance(mt5_info['count'], str) else mt5_info['count']
            db_count = db_info['count']
            
            # Check for count mismatch - even a difference of 1 is significant here
            count_diff = abs(mt5_count - db_count)
            has_discrepancy = count_diff > 0
            
            # Immediately alert if there's a significant discrepancy (more than 1 trade difference)
            # which likely indicates a system issue rather than just normal trading activity
            significant_discrepancy = count_diff >= 2
            
            # Prepare result object
            result = {
                'has_discrepancy': has_discrepancy,
                'significant_discrepancy': significant_discrepancy,
                'mt5_count': mt5_info['count'],
                'db_count': db_info['count'],
                'count_diff': count_diff,
                'mt5_last_update': mt5_info['last_update'],
                'details': {
                    'db_trades': [
                        {
                            'id': t.id,
                            'ticket': t.ticket,
                            'symbol': t.symbol,
                            'side': t.side.value if hasattr(t.side, 'value') else str(t.side),
                            'lot': t.lot,
                            'entry': t.entry,
                            'sl': t.sl,
                            'tp': t.tp,
                            'opened_at': t.opened_at.isoformat() if t.opened_at else None
                        }
                        for t in open_trades[:10]  # Limit to 10 trades for brevity
                    ]
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking trade discrepancies: {e}")
            return {
                'has_discrepancy': False,
                'error': str(e)
            }

def run_discrepancy_check():
    """
    Run the discrepancy check and send an alert if needed
    This can be called directly for testing or by the monitor
    """
    with app.app_context():
        logger.info("Running MT5 trade discrepancy check")
        
        try:
            result = check_trade_discrepancies()
            
            if result.get('has_discrepancy', False):
                # Format the alert message
                trade_details = ""
                if 'details' in result and 'db_trades' in result['details'] and result['details']['db_trades']:
                    trade_details = "\n__Database Open Trades (up to 10):__\n"
                    for t in result['details']['db_trades']:
                        trade_details += f"• {t['symbol']} {t['side']} {t['lot']} lots (Ticket: {t['ticket']})\n"
                
                # Determine alert severity based on discrepancy size
                is_significant = result.get('significant_discrepancy', False)
                
                # Use red for significant discrepancies, orange for minor ones
                alert_color = 0xFF0000 if is_significant else 0xFFA500  # Red vs Orange
                
                # Create a more urgent title for significant discrepancies
                alert_title = "CRITICAL: MT5-Database Trade Count Mismatch" if is_significant else "MT5 Trade Discrepancy Detected"
                
                # Create appropriate description based on severity
                if is_significant:
                    description = f"**URGENT: MT5 reports {result['mt5_count']} open positions, but database has {result['db_count']} open trades.**\n\n"
                    description += f"This {result['count_diff']} trade difference indicates the exit monitor may be working with incorrect data.\n\n"
                    description += f"Last MT5 update: {result['mt5_last_update']}\n"
                    description += f"{trade_details}\n\n"
                    description += f"**Action Required**: The exit monitor may attempt to close positions that no longer exist or miss positions that need to be closed."
                else:
                    description = f"**MT5 reports {result['mt5_count']} open positions, but database has {result['db_count']} open trades.**\n\n"
                    description += f"Last MT5 update: {result['mt5_last_update']}\n"
                    description += f"{trade_details}\n\n"
                    description += f"This discrepancy may indicate trades not properly tracked in the database."
                
                # Send Discord alert with appropriate severity
                send_discord_alert(
                    title=alert_title,
                    description=description,
                    alert_type="db_discrepancy",
                    color=alert_color
                )
                
                if is_significant:
                    logger.error(f"CRITICAL trade discrepancy detected: MT5={result['mt5_count']}, DB={result['db_count']}")
                else:
                    logger.warning(f"Trade discrepancy detected: MT5={result['mt5_count']}, DB={result['db_count']}")
            else:
                logger.info("No trade discrepancies found")
                
        except Exception as e:
            logger.error(f"Error in discrepancy check: {e}")

if __name__ == "__main__":
    # Run once for testing
    logger.info("Running MT5 trade discrepancy check as standalone")
    with app.app_context():
        run_discrepancy_check()