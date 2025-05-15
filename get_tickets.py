import sys
from app import app, db, Trade, TradeStatus

with app.app_context():
    open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN, account_id="163499").all()
    if open_trades:
        print("Active tickets:", [t.ticket for t in open_trades][:5])
    else:
        print("No active trades found")