#!/usr/bin/env python3
from app import app, db, Trade, TradeStatus

with app.app_context():
    open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
    print(f'Number of open trades: {len(open_trades)}')
    
    if open_trades:
        print("\nOpen trades:")
        for trade in open_trades[:10]:  # Show first 10 trades
            print(f"ID: {trade.id}, Symbol: {trade.symbol}, Ticket: {trade.ticket}, Side: {trade.side}, Opened: {trade.opened_at}")
    else:
        print("No open trades found.")