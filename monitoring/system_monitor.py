#!/usr/bin/env python3
"""
System Monitoring - Main Module
Monitors trading platform for critical issues and sends alerts via Discord
"""
import os
import logging
import datetime
from app import app, db, Trade, TradeStatus, Settings, Log, LogLevel
from monitoring.discord_alerts import send_discord_alert

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_mt5_connection():
    """
    Check if MT5 connection is active based on last heartbeat timestamp
    """
    with app.app_context():
        try:
            last_update = Settings.get_value('mt5_account', 'last_update', None)
            
            if not last_update:
                logger.info("MT5 connection has never been established")
                return
            
            try:
                last_time = datetime.datetime.fromisoformat(last_update)
                time_diff = (datetime.datetime.now() - last_time).total_seconds() / 60
                
                if time_diff > 5:  # Alert if no updates in 5+ minutes
                    send_discord_alert(
                        title="MT5 Connection Lost",
                        description=f"No MT5 heartbeat received in the last {time_diff:.1f} minutes.\n"
                                   f"Last update: {last_update}\n\n"
                                   f"Please check your MT5 terminal and the EA configuration.",
                        alert_type="mt5_connection"
                    )
            except Exception as e:
                logger.error(f"Error parsing MT5 last update timestamp: {e}")
                
        except Exception as e:
            logger.error(f"Error checking MT5 connection: {e}")

def check_trade_discrepancies():
    """
    Check for discrepancies between MT5 open trades and database records
    """
    with app.app_context():
        try:
            # Get MT5 reported open positions count
            mt5_open_positions = Settings.get_value('mt5_account', 'open_positions', 0)
            
            # Handle type conversion for count comparison
            if isinstance(mt5_open_positions, str):
                mt5_open_positions = int(mt5_open_positions)
            
            # Count open trades in database
            db_open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
            
            # Get open trades for details
            open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
            
            # Check for significant discrepancy (more than 1 trade difference)
            count_diff = abs(mt5_open_positions - db_open_trades)
            has_discrepancy = count_diff > 0
            significant_discrepancy = count_diff >= 2
            
            if has_discrepancy:
                # Format the alert message
                trade_details = ""
                if open_trades:
                    trade_details = "\n__Database Open Trades (up to 10):__\n"
                    for t in open_trades[:10]:  # Limit to 10 trades for brevity
                        side_str = t.side.value if hasattr(t.side, 'value') else str(t.side)
                        trade_details += f"• {t.symbol} {side_str} {t.lot} lots (Ticket: {t.ticket})\n"
                
                # Determine alert severity based on discrepancy size
                alert_color = 0xFF0000 if significant_discrepancy else 0xFFA500  # Red vs Orange
                
                # Create a more urgent title for significant discrepancies
                alert_title = "CRITICAL: MT5-Database Trade Count Mismatch" if significant_discrepancy else "MT5 Trade Discrepancy Detected"
                
                # Create appropriate description based on severity
                if significant_discrepancy:
                    description = f"**URGENT: MT5 reports {mt5_open_positions} open positions, but database has {db_open_trades} open trades.**\n\n"
                    description += f"This {count_diff} trade difference indicates the exit monitor may be working with incorrect data.\n\n"
                    description += f"Last MT5 update: {Settings.get_value('mt5_account', 'last_update', 'Unknown')}\n"
                    description += f"{trade_details}\n\n"
                    description += f"**Action Required**: The exit monitor may attempt to close positions that no longer exist or miss positions that need to be closed."
                else:
                    description = f"**MT5 reports {mt5_open_positions} open positions, but database has {db_open_trades} open trades.**\n\n"
                    description += f"Last MT5 update: {Settings.get_value('mt5_account', 'last_update', 'Unknown')}\n"
                    description += f"{trade_details}\n\n"
                    description += f"This discrepancy may indicate trades not properly tracked in the database."
                
                # Send Discord alert with appropriate severity
                send_discord_alert(
                    title=alert_title,
                    description=description,
                    alert_type="db_discrepancy",
                    color=alert_color
                )
                
                if significant_discrepancy:
                    logger.error(f"CRITICAL trade discrepancy detected: MT5={mt5_open_positions}, DB={db_open_trades}")
                else:
                    logger.warning(f"Trade discrepancy detected: MT5={mt5_open_positions}, DB={db_open_trades}")
            
        except Exception as e:
            logger.error(f"Error checking trade discrepancies: {e}")

def check_exit_system_failures():
    """
    Check for exit system failures by looking at recent error logs
    """
    with app.app_context():
        try:
            # Components to monitor for exit system
            exit_system_components = [
                'create_exit_monitor',
                'position_manager',
                'ml.exit_inference',
                'mt5_ea_api'
            ]
            
            # Look for exit system errors in the last 2 hours
            two_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=2)
            
            # Get exit system error logs
            error_logs = db.session.query(Log).filter(
                Log.source.in_(exit_system_components),
                Log.level.in_([LogLevel.ERROR, LogLevel.CRITICAL]),
                Log.ts > two_hours_ago
            ).order_by(Log.ts.desc()).all()
            
            # Check if we should alert
            if len(error_logs) > 0:
                # Count errors by component
                error_counts = {}
                for component in exit_system_components:
                    error_counts[component] = 0
                
                for log in error_logs:
                    if log.source in error_counts:
                        error_counts[log.source] += 1
                
                # Format alert message
                message = f"**Exit System Errors:** {len(error_logs)} errors detected in the last 2 hours.\n\n"
                    
                # Add component breakdown
                message += "__Error count by component:__\n"
                for component, count in error_counts.items():
                    if count > 0:
                        message += f"• {component}: {count} errors\n"
                
                # Add recent error examples
                if error_logs:
                    message += "\n__Recent error messages:__\n"
                    for log in error_logs[:5]:  # Limit to 5 most recent errors
                        message += f"• {log.source}: {log.message}\n"
                
                # Add message about missing ExitNet models if applicable
                missing_model_logs = [log for log in error_logs if "Missing ExitNet model" in log.message]
                if missing_model_logs:
                    missing_models = set()
                    for log in missing_model_logs:
                        # Extract model name from message like "Missing ExitNet model: /path/to/EURUSD_H1_exit.pkl"
                        if ":" in log.message:
                            model_path = log.message.split(":", 1)[1].strip()
                            if "/" in model_path:
                                model_name = model_path.split("/")[-1]
                                missing_models.add(model_name)
                    
                    if missing_models:
                        message += "\n**Missing Exit Models:**\n"
                        for model in missing_models:
                            message += f"• {model}\n"
                
                # Send Discord alert
                send_discord_alert(
                    title="Exit System Failure Detected",
                    description=message + "\n" +
                               "This may prevent trades from being closed properly. Manual intervention may be required.",
                    alert_type="exit_system",
                    color=0xFF0000  # Red for critical issues
                )
                
                logger.warning("Exit system issues detected, alert sent")
                
        except Exception as e:
            logger.error(f"Error checking exit system failures: {e}")

def check_critical_db_errors():
    """
    Check for critical database errors
    """
    with app.app_context():
        try:
            # Look for database-related errors in the last hour
            one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
            
            db_errors = db.session.query(Log).filter(
                Log.message.like('%database%'),
                Log.level.in_([LogLevel.ERROR, LogLevel.CRITICAL]),
                Log.ts > one_hour_ago
            ).count()
            
            if db_errors >= 3:  # Alert after 3+ DB errors in 1 hour
                send_discord_alert(
                    title="Critical Database Errors",
                    description=f"{db_errors} database errors detected in the last hour.\n\n"
                               f"This may indicate database connection issues or query failures.\n"
                               f"Check the application logs for more details.",
                    alert_type="critical_error"
                )
                
        except Exception as e:
            logger.error(f"Error checking database errors: {e}")

def run_monitoring_checks():
    """
    Run all monitoring checks in sequence
    This function will be called by the scheduler
    """
    logger.info("Running system monitoring checks")
    
    try:
        # Check MT5 connection status
        check_mt5_connection()
        
        # Check for trade discrepancies
        check_trade_discrepancies()
        
        # Check for exit system failures
        check_exit_system_failures()
        
        # Check for critical database errors
        check_critical_db_errors()
        
        logger.info("System monitoring checks completed")
        
    except Exception as e:
        logger.error(f"Error running monitoring checks: {e}")
        
        # Try to send an alert about the monitoring system failure
        try:
            send_discord_alert(
                title="Monitoring System Failure",
                description=f"The monitoring system itself encountered an error:\n\n```\n{str(e)}\n```\n\n"
                           f"Please check the application logs for more details.",
                alert_type="critical_error"
            )
        except Exception:
            # Last resort logging if even the alert fails
            logger.critical("Failed to send alert about monitoring system failure", exc_info=True)

if __name__ == "__main__":
    # Run once for testing
    logger.info("Running system monitoring as standalone")
    with app.app_context():
        run_monitoring_checks()