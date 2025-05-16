#!/usr/bin/env python3
"""
Check the exit system for failures
Detects issues with the trade exit monitoring system
"""
import os
import logging
import datetime
from app import app, db, Log, LogLevel
from discord_monitor import send_discord_alert

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Components to monitor for exit system
EXIT_SYSTEM_COMPONENTS = [
    'create_exit_monitor',
    'position_manager',
    'ml.exit_inference',
    'mt5_ea_api'
]

def check_exit_system_health():
    """
    Check for issues with the exit system by analyzing recent logs
    """
    with app.app_context():
        try:
            # Get logs from the last 2 hours
            two_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=2)
            
            # Get exit system error logs
            error_logs = db.session.query(Log).filter(
                Log.source.in_(EXIT_SYSTEM_COMPONENTS),
                Log.level.in_([LogLevel.ERROR, LogLevel.CRITICAL]),
                Log.ts > two_hours_ago
            ).order_by(Log.ts.desc()).all()
            
            # Count errors by component
            error_counts = {}
            for component in EXIT_SYSTEM_COMPONENTS:
                error_counts[component] = 0
            
            for log in error_logs:
                if log.source in error_counts:
                    error_counts[log.source] += 1
            
            # Prepare result
            result = {
                'has_issues': len(error_logs) > 0,
                'error_count': len(error_logs),
                'component_errors': error_counts,
                'recent_errors': [
                    {
                        'timestamp': log.ts.isoformat(),
                        'source': log.source,
                        'message': log.message
                    }
                    for log in error_logs[:5]  # Limit to 5 most recent errors
                ]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking exit system health: {e}")
            return {
                'has_issues': False,
                'error': str(e)
            }

def check_pending_exit_queue():
    """
    Check if there are trades stuck in the exit queue
    """
    with app.app_context():
        try:
            # Check if we can access the pending_closures from mt5_ea_api
            from mt5_ea_api import pending_closures
            
            pending_count = len(pending_closures) if pending_closures else 0
            
            # If there are pending closures older than 30 minutes, that's a concern
            old_closures = 0
            current_time = datetime.datetime.now()
            
            for ticket, data in pending_closures.items():
                if 'timestamp' in data:
                    timestamp = data['timestamp']
                    if isinstance(timestamp, str):
                        try:
                            timestamp = datetime.datetime.fromisoformat(timestamp)
                        except ValueError:
                            # If we can't parse the timestamp, assume it's old
                            old_closures += 1
                            continue
                    
                    time_diff = (current_time - timestamp).total_seconds() / 60
                    if time_diff > 30:  # Older than 30 minutes
                        old_closures += 1
            
            result = {
                'has_issues': old_closures > 0,
                'pending_count': pending_count,
                'old_closures': old_closures,
                'pending_tickets': list(pending_closures.keys()) if pending_closures else []
            }
            
            return result
            
        except Exception as e:
            logger.info(f"Could not check pending closures: {e}")
            return {
                'has_issues': False,
                'error': str(e),
                'pending_count': 0
            }

def run_exit_system_check():
    """
    Run both exit system health checks and send alerts if needed
    """
    with app.app_context():
        logger.info("Running exit system health check")
        
        try:
            # Check exit system logs for errors
            health_result = check_exit_system_health()
            
            # Check for pending exit queue issues
            queue_result = check_pending_exit_queue()
            
            # Determine if we need to send an alert
            system_has_issues = health_result.get('has_issues', False)
            queue_has_issues = queue_result.get('has_issues', False)
            
            if system_has_issues or queue_has_issues:
                # Format alert message
                message = ""
                
                if system_has_issues:
                    message += f"**Exit System Errors:** {health_result['error_count']} errors detected in the last 2 hours.\n\n"
                    
                    # Add component breakdown
                    message += "__Error count by component:__\n"
                    for component, count in health_result['component_errors'].items():
                        if count > 0:
                            message += f"• {component}: {count} errors\n"
                    
                    # Add recent error examples
                    if health_result.get('recent_errors'):
                        message += "\n__Recent error messages:__\n"
                        for error in health_result['recent_errors']:
                            message += f"• {error['source']}: {error['message']}\n"
                
                if queue_has_issues:
                    if system_has_issues:
                        message += "\n"  # Add separator if we already have error info
                    
                    message += f"**Exit Queue Issues:** {queue_result['old_closures']} trades have been stuck in the closure queue for over 30 minutes.\n"
                    message += f"Total pending closures: {queue_result['pending_count']}\n"
                    
                    if queue_result.get('pending_tickets'):
                        message += "\n__Pending ticket numbers:__\n"
                        message += ", ".join(map(str, queue_result['pending_tickets'][:10]))
                        if len(queue_result['pending_tickets']) > 10:
                            message += f" and {len(queue_result['pending_tickets']) - 10} more"
                
                # Send Discord alert
                send_discord_alert(
                    title="Exit System Failure Detected",
                    description=message + "\n\n" +
                               "This may prevent trades from being closed properly. Manual intervention may be required.",
                    alert_type="exit_system",
                    color=0xFF0000  # Red for critical issues
                )
                
                logger.warning("Exit system issues detected, alert sent")
            else:
                logger.info("No exit system issues found")
                
        except Exception as e:
            logger.error(f"Error in exit system check: {e}")

if __name__ == "__main__":
    # Run once for testing
    logger.info("Running exit system check as standalone")
    with app.app_context():
        run_exit_system_check()