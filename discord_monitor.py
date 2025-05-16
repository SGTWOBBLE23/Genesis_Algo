#!/usr/bin/env python3
"""
Discord Monitor Service
Provides webhook-based notification for critical system issues in the Genesis Trading Platform
"""
import os
import json
import logging
import datetime
import requests
from app import app, db, Trade, TradeStatus, Settings, Log, LogLevel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Discord webhook configuration
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1372819541452918854/cBkmSNVursWI5S_KmNy7b-hG3LAntEDeojuOcwf4Nwi5F2MIiq7nqRm3Uw8jJVlLZR57"

# Environment variable override for testing
if os.environ.get("DISCORD_WEBHOOK_URL"):
    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Monitoring thresholds
MT5_HEARTBEAT_THRESHOLD_MINUTES = 5  # Alert if no MT5 updates in 5 minutes
DB_ERROR_ALERT_THRESHOLD = 3  # Alert after 3 database errors in short succession

# Error tracking to prevent alert spam
recent_alerts = {
    "mt5_connection": datetime.datetime.min,
    "db_discrepancy": datetime.datetime.min,
    "exit_system": datetime.datetime.min,
    "critical_error": datetime.datetime.min
}

# Minimum time between similar alerts (in minutes)
ALERT_COOLDOWN_MINUTES = 30

def send_discord_alert(title, description, alert_type, color=0xFF0000):
    """
    Send an alert to Discord using webhook
    
    Args:
        title: Alert title
        description: Alert description
        alert_type: Category of alert for rate limiting
        color: Embed color (red by default)
    """
    # Check alert cooldown
    now = datetime.datetime.now()
    if alert_type in recent_alerts:
        last_alert_time = recent_alerts[alert_type]
        time_diff = (now - last_alert_time).total_seconds() / 60
        
        if time_diff < ALERT_COOLDOWN_MINUTES:
            logger.info(f"Skipping {alert_type} alert due to cooldown ({time_diff:.1f} min < {ALERT_COOLDOWN_MINUTES} min)")
            return False
    
    # Update last alert time
    recent_alerts[alert_type] = now
    
    # Prepare webhook payload
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    
    payload = {
        "embeds": [
            {
                "title": f"🚨 {title}",
                "description": description,
                "color": color,
                "footer": {
                    "text": f"Genesis Trading Platform | {timestamp}"
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 204:
            logger.info(f"Discord alert sent successfully: {title}")
            
            # Log the alert in the database for record keeping
            with app.app_context():
                Log.add(
                    level=LogLevel.WARNING,
                    source="discord_monitor",
                    message=f"Discord alert: {title}",
                    context={"description": description, "type": alert_type}
                )
            
            return True
        else:
            logger.error(f"Failed to send Discord alert: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Discord alert: {e}")
        return False

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
                
                if time_diff > MT5_HEARTBEAT_THRESHOLD_MINUTES:
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
            
            # Count open trades in database
            db_open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
            
            # Check for significant discrepancy (more than 1 trade difference)
            if abs(mt5_open_positions - db_open_trades) > 1:
                send_discord_alert(
                    title="Trade Discrepancy Detected",
                    description=f"Discrepancy between MT5 open positions ({mt5_open_positions}) "
                               f"and database open trades ({db_open_trades}).\n\n"
                               f"This may indicate trades not properly tracked in the database.",
                    alert_type="db_discrepancy"
                )
                
        except Exception as e:
            logger.error(f"Error checking trade discrepancies: {e}")

def check_exit_system_failures():
    """
    Check for exit system failures by looking at recent error logs
    """
    with app.app_context():
        try:
            # Look for exit system errors in the last hour
            one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
            
            exit_errors = db.session.query(Log).filter(
                Log.source.in_(['create_exit_monitor', 'position_manager', 'ml.exit_inference']),
                Log.level.in_([LogLevel.ERROR, LogLevel.CRITICAL]),
                Log.ts > one_hour_ago
            ).count()
            
            if exit_errors > 0:
                send_discord_alert(
                    title="Exit System Failures Detected",
                    description=f"{exit_errors} exit system errors detected in the last hour.\n\n"
                               f"This may prevent trades from being closed properly.\n"
                               f"Check the application logs for more details.",
                    alert_type="exit_system"
                )
                
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
            
            if db_errors >= DB_ERROR_ALERT_THRESHOLD:
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
        
        # Use specialized modules for more detailed checks
        try:
            # Import specialized check modules
            from check_mt5_trades import run_discrepancy_check
            from check_exit_system import run_exit_system_check
            
            # Run specialized checks
            run_discrepancy_check()
            run_exit_system_check()
        except ImportError as e:
            logger.warning(f"Could not import specialized check modules: {e}")
            # Fall back to basic checks if modules not available
            check_trade_discrepancies()
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
    logger.info("Running Discord monitoring system as standalone")
    with app.app_context():
        run_monitoring_checks()