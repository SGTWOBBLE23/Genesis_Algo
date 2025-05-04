import json
import time
import logging
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
from app import db, Signal, Trade, SignalAction, TradeStatus, TradeSide, Settings, SignalStatus
from chart_utils import generate_chart

# Set up logging
logger = logging.getLogger(__name__)

# Create a blueprint for the MT5 EA API
mt5_api = Blueprint('mt5_api', __name__, url_prefix='/mt5')

# Dictionary to store active MT5 terminal connections
active_terminals = {}

# Add a route for get-signals (with hyphen) since the MT5 EA is looking for that URL
@mt5_api.route('/get-signals', methods=['POST'])
def get_signals_hyphen():
    """Redirects to get_signals, handles the hyphen vs underscore issue"""
    return get_signals()

@mt5_api.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Receive heartbeat from MT5 EA"""
    try:
        # Debug the raw request data
        raw_data = request.data
        logger.info(f"Received raw heartbeat data: {raw_data}")
        
        # Clean the input data by removing null bytes
        try:
            if b'\x00' in raw_data:
                logger.info("Found null character in the request data, cleaning it")
                clean_data = raw_data.replace(b'\x00', b'')
                # Try to parse the cleaned JSON
                data = json.loads(clean_data.decode('utf-8'))
                logger.info(f"Successfully parsed cleaned JSON: {data}")
            else:
                # Use Flask's built-in parser if no null characters
                data = request.json
                
            logger.info(f"Heartbeat received: {data}")
        except Exception as json_err:
            logger.error(f"Error parsing JSON: {str(json_err)}")
            return jsonify({"status": "error", "message": f"Invalid JSON: {str(json_err)}"}), 400
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        terminal_id = data.get('terminal_id')
        connection_time = data.get('connection_time')
        
        if not account_id or not terminal_id:
            return jsonify({"status": "error", "message": "Missing account_id or terminal_id"}), 400
        
        # Update active terminals list
        current_time = datetime.now()
        active_terminals[terminal_id] = {
            'account_id': account_id,
            'last_seen': current_time,
            'connection_time': connection_time
        }
        
        # Update settings table for dashboard monitoring
        from app import Settings
        # Store last heartbeat time as ISO formatted string
        Settings.set_value('mt5', 'last_heartbeat', current_time.isoformat())
        # Count and store number of connected terminals
        connected_terminals = len(active_terminals)
        Settings.set_value('mt5', 'connected_terminals', connected_terminals)
        # Store most recent terminal id
        Settings.set_value('mt5', 'last_terminal_id', terminal_id)
        # Store most recent account id
        Settings.set_value('mt5', 'last_account_id', account_id)
        
        logger.info(f"Heartbeat received from MT5 terminal {terminal_id} for account {account_id}")
        
        return jsonify({
            "status": "success",
            "server_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Heartbeat received"
        })
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/get_signals', methods=['POST'])
def get_signals():
    """Return new trading signals to MT5 EA"""
    try:
        # Debug the raw request data
        raw_data = request.data
        logger.info(f"Received raw signals request data: {raw_data}")
        
        # Clean the input data by removing null bytes
        try:
            if b'\x00' in raw_data:
                logger.info("Found null character in the request data, cleaning it")
                clean_data = raw_data.replace(b'\x00', b'')
                # Try to parse the cleaned JSON
                data = json.loads(clean_data.decode('utf-8'))
                logger.info(f"Successfully parsed cleaned JSON: {data}")
            else:
                # Use Flask's built-in parser if no null characters
                data = request.json
        except Exception as json_err:
            logger.error(f"Error parsing JSON: {str(json_err)}")
            return jsonify({"status": "error", "message": f"Invalid JSON: {str(json_err)}"}), 400
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        last_signal_id = data.get('last_signal_id', 0)
        symbols = data.get('symbols', [])
        
        if not account_id:
            return jsonify({"status": "error", "message": "Missing account_id"}), 400
        
        logger.info(f"MT5 EA requesting signals for account {account_id}, last_signal_id={last_signal_id}")
        
        # Log the raw data for debugging
        logger.info(f"Raw data from MT5: {data}")
        
        # Check if forex market is open
        now = datetime.now()
        is_weekend = now.weekday() >= 5  # 5 = Saturday, 6 = Sunday
        
        # Get signals from database that are in PENDING or ACTIVE status
        new_signals = []
        
        if last_signal_id > 0:
            # Only get signals with higher IDs than what MT5 already has
            new_signals = db.session.query(Signal).filter(
                Signal.id > last_signal_id,
                Signal.status.in_(['PENDING', 'ACTIVE'])
            ).order_by(Signal.id.asc()).all()
            
            # Do NOT fall back to previous signals if no new ones are found
            if not new_signals:
                logger.info(f"No new signals found after ID {last_signal_id}, returning empty list")
                return jsonify({
                    "status": "success",
                    "signals": []
                })
        else:
            # First request, return all pending/active signals
            new_signals = db.session.query(Signal).filter(
                Signal.status.in_(['PENDING', 'ACTIVE'])
            ).order_by(Signal.id.asc()).all()
        
        # Filter by market hours if needed
        if is_weekend:
            # Filter out forex pairs but keep crypto and metals
            filtered_by_market = []
            for signal in new_signals:
                # Keep crypto and precious metals
                if any(asset in signal.symbol for asset in ['BTC', 'ETH', 'XAU', 'XAG']):
                    filtered_by_market.append(signal)
                # Filter out forex pairs during weekend
                elif any(pair in signal.symbol for pair in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD']):
                    logger.info(f"Filtering out forex signal for {signal.symbol} during weekend")
                else:
                    filtered_by_market.append(signal)
            new_signals = filtered_by_market
        
        # Check if we received valid symbols array
        valid_symbols = []
        if symbols and isinstance(symbols, list):
            # Convert integer symbols to strings if necessary
            for symbol in symbols:
                if symbol and not (isinstance(symbol, int) and symbol == 0):
                    if isinstance(symbol, int):
                        # Try to convert integer to string symbol name
                        valid_symbols.append(str(symbol))
                    else:
                        valid_symbols.append(symbol)
        
        # If we have valid symbols, filter the signals we already retrieved
        filtered_signals = []
        if valid_symbols:
            logger.info(f"Filtering signals for symbols: {valid_symbols}")
            filtered_signals = [s for s in new_signals if s.symbol in valid_symbols]
        else:
            logger.info("No valid symbols received, returning available signals")
            filtered_signals = new_signals
        
        signals = filtered_signals  # Use the filtered list for formatting
        
        # Format signals for MT5 EA
        formatted_signals = []
        for signal in signals:
            # Convert SignalAction enum to string
            action = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)
            
            # Format signal data for MT5 EA, matching expected format
            formatted_signal = {
                "id": signal.id,
                "symbol": signal.symbol,  # Direct symbol without nesting in asset
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
            
            # Update signal status to indicate it has been sent to MT5
            # This prevents resending unless explicitly requested
            signal.status = 'ACTIVE'
            
        if formatted_signals:
            db.session.commit()  # Save the status changes
            logger.info(f"Sending {len(formatted_signals)} signals to MT5 terminal for account {account_id}")
        else:
            logger.info(f"No signals to send to MT5 terminal for account {account_id}")
        
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
        # Debug the raw request data
        raw_data = request.data
        logger.info(f"Received raw trade report data: {raw_data}")
        
        # Clean the input data by removing null bytes
        try:
            if b'\x00' in raw_data:
                logger.info("Found null character in the request data, cleaning it")
                clean_data = raw_data.replace(b'\x00', b'')
                # Try to parse the cleaned JSON
                data = json.loads(clean_data.decode('utf-8'))
                logger.info(f"Successfully parsed cleaned JSON: {data}")
            else:
                # Use Flask's built-in parser if no null characters
                data = request.json
                
            logger.info(f"Trade report received: {data}")
        except Exception as json_err:
            logger.error(f"Error parsing JSON: {str(json_err)}")
            return jsonify({"status": "error", "message": f"Invalid JSON: {str(json_err)}"}), 400
        
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
        # Debug the raw request data
        raw_data = request.data
        logger.info(f"Received raw trade update data: {raw_data}")
        
        # Clean the input data by removing null bytes
        try:
            if b'\x00' in raw_data:
                logger.info("Found null character in the request data, cleaning it")
                clean_data = raw_data.replace(b'\x00', b'')
                # Try to parse the cleaned JSON
                data = json.loads(clean_data.decode('utf-8'))
                logger.info(f"Successfully parsed cleaned JSON: {data}")
            else:
                # Use Flask's built-in parser if no null characters
                data = request.json
                
            logger.info(f"Trade update received: {data}")
        except Exception as json_err:
            logger.error(f"Error parsing JSON: {str(json_err)}")
            return jsonify({"status": "error", "message": f"Invalid JSON: {str(json_err)}"}), 400
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        account_id = data.get('account_id')
        trades_data = data.get('trades', {})
        
        if not account_id:
            return jsonify({"status": "error", "message": "Missing account_id"}), 400
            
        # If trades data is empty, just acknowledge the request
        if not trades_data:
            logger.info(f"No trades data for account {account_id}")
            return jsonify({
                "status": "success",
                "message": "No trades to update",
                "updated_count": 0,
                "created_count": 0
            })
        
        # Update each trade in the database
        updated_count = 0
        created_count = 0
        for ticket, trade_info in trades_data.items():
            # Find the trade by ticket
            trade = db.session.query(Trade).filter(Trade.ticket == ticket).first()
            
            # If trade doesn't exist, create it - handle field name mapping
            if not trade:
                try:
                    # Map field names from EA to our model
                    # Convert type (BUY/SELL) to side enum
                    side_value = TradeSide.BUY if trade_info.get('type', '').upper() == 'BUY' else TradeSide.SELL
                    
                    # Map open_price to entry and exit_price to exit
                    entry_value = float(trade_info.get('open_price', 0)) if trade_info.get('open_price') else None
                    exit_value = float(trade_info.get('exit_price', 0)) if trade_info.get('exit_price') else None
                    
                    # Handle other fields
                    symbol = trade_info.get('symbol', '')
                    lot = float(trade_info.get('lot', 0))
                    sl = float(trade_info.get('sl', 0)) if trade_info.get('sl') else None
                    tp = float(trade_info.get('tp', 0)) if trade_info.get('tp') else None
                    profit = float(trade_info.get('profit', 0))
                    status_str = trade_info.get('status', 'OPEN')
                    status_value = TradeStatus.CLOSED if status_str == 'CLOSED' else TradeStatus.OPEN
                    
                    # Convert timestamp strings to datetime objects
                    opened_at = None
                    closed_at = None
                    if 'opened_at' in trade_info:
                        try:
                            # Try both date formats that might come from MT5
                            try:
                                opened_at = datetime.strptime(trade_info['opened_at'], '%Y.%m.%d %H:%M:%S')
                            except ValueError:
                                opened_at = datetime.strptime(trade_info['opened_at'], '%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logger.warning(f"Failed to parse opened_at: {e}")
                    
                    if 'closed_at' in trade_info:
                        try:
                            # Try both date formats that might come from MT5
                            try:
                                closed_at = datetime.strptime(trade_info['closed_at'], '%Y.%m.%d %H:%M:%S')
                            except ValueError:
                                closed_at = datetime.strptime(trade_info['closed_at'], '%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logger.warning(f"Failed to parse closed_at: {e}")
                    
                    # Create new trade object
                    trade = Trade(
                        ticket=ticket,
                        symbol=symbol,
                        side=side_value,
                        lot=lot,
                        entry=entry_value,
                        exit=exit_value,
                        sl=sl,
                        tp=tp,
                        pnl=profit,
                        status=status_value,
                        opened_at=opened_at,
                        closed_at=closed_at
                    )
                    
                    # Add extra data to context
                    context = {}
                    context['source'] = 'mt5_import'
                    context['import_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if 'swap' in trade_info:
                        context['swap'] = float(trade_info['swap'])
                    if 'commission' in trade_info:
                        context['commission'] = float(trade_info['commission'])
                    trade.context = context
                    
                    db.session.add(trade)
                    created_count += 1
                    logger.info(f"Created new trade from MT5: {ticket} {symbol}")
                except Exception as e:
                    logger.error(f"Error creating trade {ticket}: {str(e)}")
            
            # If trade exists, update it
            elif trade:  
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
                
                # Handle open_price and exit_price mapping
                if 'open_price' in trade_info:
                    trade.entry = float(trade_info['open_price'])
                if 'exit_price' in trade_info:
                    trade.exit = float(trade_info['exit_price'])
                
                # Update opened_at timestamp if it's in the incoming data and missing in our record
                if 'opened_at' in trade_info and trade_info['opened_at'] and (trade.opened_at is None):
                    try:
                        # Try MT5 format first (YYYY.MM.DD HH:MM:SS)
                        trade.opened_at = datetime.strptime(trade_info['opened_at'], '%Y.%m.%d %H:%M:%S')
                        logger.info(f"Using original opened_at time from MT5: {trade.opened_at}")
                    except ValueError:
                        try:
                            # Try ISO format as fallback (YYYY-MM-DD HH:MM:SS)
                            trade.opened_at = datetime.strptime(trade_info['opened_at'], '%Y-%m-%d %H:%M:%S')
                            logger.info(f"Using parsed opened_at time: {trade.opened_at}")
                        except ValueError as e:
                            logger.error(f"Error parsing opened_at date: {e}. Not updating.")
                
                # Update trade status if it has changed
                if 'status' in trade_info and trade_info['status'] != 'OPEN':
                    trade.status = TradeStatus(trade_info['status'])
                    if trade_info['status'] == 'CLOSED':
                        # Only set closed_at if it's not already in trade_info
                        if 'closed_at' in trade_info and trade_info['closed_at']:
                            try:
                                # Try MT5 format first (YYYY.MM.DD HH:MM:SS)
                                trade.closed_at = datetime.strptime(trade_info['closed_at'], '%Y.%m.%d %H:%M:%S')
                                logger.info(f"Using original closed_at time from MT5: {trade.closed_at}")
                            except ValueError:
                                try:
                                    # Try ISO format as fallback (YYYY-MM-DD HH:MM:SS)
                                    trade.closed_at = datetime.strptime(trade_info['closed_at'], '%Y-%m-%d %H:%M:%S')
                                    logger.info(f"Using parsed closed_at time: {trade.closed_at}")
                                except ValueError as e:
                                    logger.error(f"Error parsing closed_at date: {e}. Using current time.")
                                    trade.closed_at = datetime.now()
                        else:
                            # Fallback to current time if no closed_at in payload
                            trade.closed_at = datetime.now()
                            logger.info("No closed_at time in payload, using current time")
                
                # Update context with additional info
                context = trade.context if hasattr(trade, 'context') and trade.context else {}
                context['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if 'swap' in trade_info:
                    context['swap'] = float(trade_info['swap'])
                if 'commission' in trade_info:
                    context['commission'] = float(trade_info['commission'])
                trade.context = context
                
                updated_count += 1
        
        if updated_count > 0 or created_count > 0:
            db.session.commit()
            logger.info(f"Updated {updated_count} and created {created_count} trades for account {account_id}")
        
        return jsonify({
            "status": "success",
            "updated_count": updated_count,
            "created_count": created_count,
            "message": f"Updated {updated_count} and created {created_count} trades"
        })
        
    except Exception as e:
        logger.error(f"Error updating trades: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/signal_chart/<int:signal_id>', methods=['GET'])
def signal_chart(signal_id):
    """Generate a chart for a specific signal ID"""
    try:
        # Find the signal
        signal = db.session.query(Signal).filter_by(id=signal_id).first()
        
        if not signal:
            return jsonify({"status": "error", "message": f"Signal with ID {signal_id} not found"}), 404
        
        # Determine result type based on signal status
        result = "anticipated"
        if signal.status == SignalStatus.TRIGGERED:
            result = "win" if signal.context and signal.context.get("pnl", 0) > 0 else "loss"
        elif signal.status == SignalStatus.ACTIVE:
            result = "active"
        elif signal.status == SignalStatus.PENDING:
            result = "pending"
        
        # Get current datetime for entry point (or use signal created_at)
        entry_time = datetime.now()
        
        # Generate the chart
        chart_path = generate_chart(
            symbol=signal.symbol,
            timeframe="H1",  # Default to H1 timeframe
            count=100,      # Default to 100 candles
            entry_point=(entry_time, signal.entry) if signal.entry else None,
            stop_loss=signal.sl,
            take_profit=signal.tp,
            result=result
        )
        
        if not chart_path or not os.path.exists(chart_path):
            return jsonify({"status": "error", "message": "Failed to generate chart"}), 500
        
        return send_file(chart_path, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error generating signal chart: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@mt5_api.route('/account_status', methods=['POST'])
def account_status():
    """Receive account status updates from MT5 EA"""
    try:
        # Debug the raw request data
        raw_data = request.data
        logger.info(f"Received raw account status data: {raw_data}")
        
        # Clean the input data by removing null bytes
        try:
            if b'\x00' in raw_data:
                logger.info("Found null character in the request data, cleaning it")
                clean_data = raw_data.replace(b'\x00', b'')
                # Try to parse the cleaned JSON
                data = json.loads(clean_data.decode('utf-8'))
                logger.info(f"Successfully parsed cleaned JSON: {data}")
            else:
                # Use Flask's built-in parser if no null characters
                data = request.json
                
            logger.info(f"Account status update received: {data}")
        except Exception as json_err:
            logger.error(f"Error parsing JSON: {str(json_err)}")
            return jsonify({"status": "error", "message": f"Invalid JSON: {str(json_err)}"}), 400
        
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
        
        # Store account status in Settings
        from app import Settings
        
        # Store latest account stats in settings table
        if balance is not None:
            Settings.set_value('mt5_account', 'balance', float(balance))
        if equity is not None:
            Settings.set_value('mt5_account', 'equity', float(equity))
        if margin is not None:
            Settings.set_value('mt5_account', 'margin', float(margin))
        if free_margin is not None:
            Settings.set_value('mt5_account', 'free_margin', float(free_margin))
        if leverage is not None:
            Settings.set_value('mt5_account', 'leverage', leverage)
        if open_positions is not None:
            Settings.set_value('mt5_account', 'open_positions', open_positions)
        
        # Store the last update time
        Settings.set_value('mt5_account', 'last_update', datetime.now().isoformat())
        # Store the account ID
        Settings.set_value('mt5_account', 'id', account_id)
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
