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
ALERT_COOLDOWN_MINUTES = 10

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