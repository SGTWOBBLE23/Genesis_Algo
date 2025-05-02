import json
import time
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db, Signal, Trade, SignalAction, TradeStatus, TradeSide

# Set up logging
logger = logging.getLogger(__name__)

# Create a blueprint for the MT5 EA API
mt5_api = Blueprint('mt5_api', __name__, url_prefix='/mt5_ea_api')

# Dictionary to store active MT5 terminal connections
active_terminals = {}

@mt5_api.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Receive heartbeat from MT5 EA"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        terminal_id = data.get('terminal_id')
        connection_time = data.get('connection_time')
        
        if not account_id or not terminal_id:
            return jsonify({"status": "error", "message": "Missing account_id or terminal_id"}), 400
        
        # Update active terminals list
        active_terminals[terminal_id] = {
            'account_id': account_id,
            'last_seen': datetime.now(),
            'connection_time': connection_time
        }
        
        logger.info(f"Heartbeat received from MT5 terminal {terminal_id} for account {account_id}")
        
        return jsonify({
            "status": "success",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Heartbeat received"
        })
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/get_signals', methods=['POST'])
def get_signals():
    """Return new trading signals to MT5 EA"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        last_signal_id = data.get('last_signal_id', 0)
        symbols = data.get('symbols', [])
        
        if not account_id:
            return jsonify({"status": "error", "message": "Missing account_id"}), 400
        
        # Get new signals from database
        signals_query = db.session.query(Signal).filter(
            Signal.id > last_signal_id,
            Signal.status.in_(['PENDING', 'ACTIVE'])
        )
        
        # Filter by symbols if provided
        if symbols and len(symbols) > 0:
            signals_query = signals_query.filter(Signal.symbol.in_(symbols))
        
        signals = signals_query.order_by(Signal.id.asc()).all()
        
        # Format signals for MT5 EA
        formatted_signals = []
        for signal in signals:
            # Convert SignalAction enum to string
            action = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)
            
            # Format signal data for MT5
            formatted_signal = {
                "id": signal.id,
                "asset": {
                    "symbol": signal.symbol
                },
                "action": action,
                "entry_price": float(signal.entry) if signal.entry else 0.0,
                "stop_loss": float(signal.sl) if signal.sl else 0.0,
                "take_profit": float(signal.tp) if signal.tp else 0.0,
                "confidence": float(signal.confidence),
                "position_size": 0.1,  # Default lot size
                "force_execution": False
            }
            
            # Get additional context from signal if available
            if hasattr(signal, 'context') and signal.context:
                # Include any additional context data MT5 might need
                if isinstance(signal.context, dict) and 'position_size' in signal.context:
                    formatted_signal["position_size"] = float(signal.context['position_size'])
                if isinstance(signal.context, dict) and 'force_execution' in signal.context:
                    formatted_signal["force_execution"] = bool(signal.context['force_execution'])
            
            formatted_signals.append(formatted_signal)
        
        logger.info(f"Sending {len(formatted_signals)} signals to MT5 terminal for account {account_id}")
        
        return jsonify({
            "status": "success",
            "signals": formatted_signals
        })
        
    except Exception as e:
        logger.error(f"Error getting signals: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/trade_report', methods=['POST'])
def trade_report():
    """Receive trade execution reports from MT5 EA"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        signal_id = data.get('signal_id')
        account_id = data.get('account_id')
        symbol = data.get('symbol')
        action = data.get('action')
        ticket = data.get('ticket')
        lot_size = data.get('lot_size')
        entry_price = data.get('entry_price')
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')
        execution_time = data.get('execution_time')
        status = data.get('status')  # success, error, pending
        message = data.get('message', '')
        
        if not account_id or not symbol or not action or not status:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Update signal status if signal_id is provided
        if signal_id:
            signal = db.session.query(Signal).filter(Signal.id == signal_id).first()
            if signal:
                if status == 'success':
                    signal.status = 'TRIGGERED'
                elif status == 'error':
                    signal.status = 'ERROR'
                elif status == 'pending':
                    signal.status = 'PENDING'
                
                # Store message in context
                if not hasattr(signal, 'context') or not signal.context:
                    signal.context = {}
                signal.context['execution_message'] = message
                signal.context['execution_status'] = status
                signal.context['execution_time'] = execution_time
                
                db.session.commit()
        
        # Create a trade record if status is success
        if status == 'success' and ticket:
            # Determine trade side from action
            side = TradeSide.BUY
            if 'SELL' in action or 'SHORT' in action:
                side = TradeSide.SELL
            
            # Create new trade
            trade = Trade(
                signal_id=signal_id,
                ticket=ticket,
                symbol=symbol,
                side=side,
                lot=float(lot_size),
                entry=float(entry_price) if entry_price else None,
                sl=float(stop_loss) if stop_loss else None,
                tp=float(take_profit) if take_profit else None,
                status=TradeStatus.OPEN,
                opened_at=datetime.strptime(execution_time, "%Y-%m-%d %H:%M:%S") if execution_time else datetime.now(),
                context={'account_id': account_id, 'execution_message': message}
            )
            
            db.session.add(trade)
            db.session.commit()
            
            logger.info(f"Trade recorded: Ticket {ticket}, Symbol {symbol}, Side {side}")
        
        return jsonify({
            "status": "success",
            "message": "Trade report received"
        })
        
    except Exception as e:
        logger.error(f"Error processing trade report: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/update_trades', methods=['POST'])
def update_trades():
    """Receive updates on open trades from MT5 EA"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        trades_data = data.get('trades', {})
        
        if not account_id or not trades_data:
            return jsonify({"status": "error", "message": "Missing account_id or trades data"}), 400
        
        # Update each trade in the database
        updated_count = 0
        for ticket, trade_info in trades_data.items():
            # Find the trade by ticket
            trade = db.session.query(Trade).filter(Trade.ticket == ticket).first()
            
            if trade:
                # Update trade information
                if 'current_price' in trade_info:
                    # Calculate PnL
                    current_price = float(trade_info['current_price'])
                    entry_price = trade.entry
                    lot_size = trade.lot
                    
                    if entry_price and trade.side == TradeSide.BUY:
                        pnl = (current_price - entry_price) * lot_size * 100000  # Basic pnl calculation
                    elif entry_price and trade.side == TradeSide.SELL:
                        pnl = (entry_price - current_price) * lot_size * 100000  # Basic pnl calculation
                    else:
                        pnl = float(trade_info.get('profit', 0))
                    
                    trade.pnl = pnl
                
                # Update other fields if provided
                if 'sl' in trade_info:
                    trade.sl = float(trade_info['sl']) if trade_info['sl'] else None
                if 'tp' in trade_info:
                    trade.tp = float(trade_info['tp']) if trade_info['tp'] else None
                
                # Update trade status if it has changed
                if 'status' in trade_info and trade_info['status'] != 'OPEN':
                    trade.status = TradeStatus(trade_info['status'])
                    if trade_info['status'] == 'CLOSED':
                        trade.closed_at = datetime.now()
                
                # Update context with additional info
                context = trade.context if hasattr(trade, 'context') and trade.context else {}
                context['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if 'swap' in trade_info:
                    context['swap'] = float(trade_info['swap'])
                if 'commission' in trade_info:
                    context['commission'] = float(trade_info['commission'])
                trade.context = context
                
                updated_count += 1
        
        if updated_count > 0:
            db.session.commit()
            logger.info(f"Updated {updated_count} trades for account {account_id}")
        
        return jsonify({
            "status": "success",
            "updated_count": updated_count,
            "message": f"Updated {updated_count} trades"
        })
        
    except Exception as e:
        logger.error(f"Error updating trades: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/account_status', methods=['POST'])
def account_status():
    """Receive account status updates from MT5 EA"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        balance = data.get('balance')
        equity = data.get('equity')
        margin = data.get('margin')
        free_margin = data.get('free_margin')
        leverage = data.get('leverage')
        open_positions = data.get('open_positions')
        
        if not account_id:
            return jsonify({"status": "error", "message": "Missing account_id"}), 400
        
        # Store account status in session or database
        # For now, we'll just store it in memory
        active_terminals[account_id] = {
            'last_update': datetime.now(),
            'balance': balance,
            'equity': equity,
            'margin': margin,
            'free_margin': free_margin,
            'leverage': leverage,
            'open_positions': open_positions
        }
        
        logger.info(f"Account status updated for {account_id}: Balance {balance}, Equity {equity}")
        
        return jsonify({
            "status": "success",
            "message": "Account status updated"
        })
        
    except Exception as e:
        logger.error(f"Error updating account status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
