#!/usr/bin/env python3
"""
Send a test alert to verify Discord webhook integration
"""
import logging
from app import app
from discord_monitor import send_discord_alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_test_alert():
    """Send a test alert to Discord webhook"""
    with app.app_context():
        success = send_discord_alert(
            title="Genesis Trading Monitor: Test Alert",
            description="This is a test alert from your Genesis Trading Platform.\n\n"
                      "If you're seeing this message, the Discord monitoring system is working correctly!\n\n"
                      "The monitor will alert you about:\n"
                      "• MT5 connection failures\n"
                      "• Trade discrepancies\n"
                      "• Exit system failures\n"
                      "• Critical database errors\n\n"
                      "Alert cooldown is set to 10 minutes.",
            alert_type="test",
            color=0x00FF00  # Green color for test message
        )
        
        if success:
            logger.info("Test alert sent successfully to Discord!")
        else:
            logger.error("Failed to send test alert to Discord.")

if __name__ == "__main__":
    logger.info("Sending test alert to Discord webhook...")
    send_test_alert()