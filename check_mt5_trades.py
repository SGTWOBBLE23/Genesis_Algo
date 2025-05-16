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
            
            # Check for count mismatch
            count_diff = abs(mt5_info['count'] - db_info['count'])
            has_discrepancy = count_diff > 0
            
            # Prepare result object
            result = {
                'has_discrepancy': has_discrepancy,
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
                
                # Send Discord alert
                send_discord_alert(
                    title="MT5 Trade Discrepancy Detected",
                    description=f"**MT5 reports {result['mt5_count']} open positions, but database has {result['db_count']} open trades.**\n\n"
                               f"Last MT5 update: {result['mt5_last_update']}\n"
                               f"{trade_details}\n\n"
                               f"This discrepancy may indicate trades not properly tracked in the database.",
                    alert_type="db_discrepancy",
                    color=0xFFA500  # Orange color for warnings
                )
                
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