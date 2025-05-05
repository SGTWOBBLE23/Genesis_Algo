#!/usr/bin/env python3

"""
Cancel All Signals Script

This script will mark all PENDING and ACTIVE signals as CANCELLED.
Use this to clear your dashboard and MT5 charts of old signals.
"""

import os
from app import app, db, Signal, SignalStatus

# Main execution
if __name__ == '__main__':
    with app.app_context():
        try:
            # Get all pending and active signals
            active_signals = Signal.query.filter(
                Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
            ).all()
            
            print(f"Found {len(active_signals)} active signals")
            
            # Mark all as cancelled
            for signal in active_signals:
                signal.status = SignalStatus.CANCELLED
                print(f"Cancelled signal {signal.id} for {signal.symbol}")
            
            # Commit the changes
            db.session.commit()
            print("All signals have been cancelled successfully!")
            print("\nRefresh your dashboard to see the changes.\n")
            print("If lines still appear on your MT5 chart, you may need to restart MT5 or clear the chart manually.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error cancelling signals: {str(e)}")
