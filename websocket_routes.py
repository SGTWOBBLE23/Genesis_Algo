import logging
import json
import queue
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Create a queue for signals to be sent to connected clients
signals_queue = queue.Queue()

def register(app, sock):
    """
    Register websocket routes with the application.
    
    Args:
        app: Flask application instance
        sock: Flask-Sock instance
    """
    
    @sock.route('/ws/trades')
    def ws_trades(ws):
        """WebSocket endpoint for live trade updates"""
        logger.info("Client connected to trades websocket")
        try:
            # Send initial message
            ws.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.now().isoformat()
            }))
            
            # Keep connection alive
            while True:
                # This will block until the client sends a message
                message = ws.receive()
                
                # Process client message if needed
                try:
                    data = json.loads(message)
                    logger.info(f"Received message from client: {data}")
                    
                    # Echo back to confirm receipt
                    ws.send(json.dumps({
                        "type": "confirmation",
                        "received": data,
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception as e:
                    logger.error(f"Error processing client message: {str(e)}")
                    ws.send(json.dumps({
                        "type": "error",
                        "message": f"Failed to process message: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }))
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
    
    @sock.route('/ws/signals')
    def ws_signals(ws):
        """WebSocket endpoint for live trading signals"""
        logger.info("Client connected to signals websocket")
        try:
            # Send initial message
            ws.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.now().isoformat()
            }))
            
            # Keep connection alive
            while True:
                # This will block until the client sends a message
                message = ws.receive()
                
                # Process client message if needed
                try:
                    data = json.loads(message)
                    logger.info(f"Received message from client: {data}")
                    
                    # Echo back to confirm receipt
                    ws.send(json.dumps({
                        "type": "confirmation",
                        "received": data,
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception as e:
                    logger.error(f"Error processing client message: {str(e)}")
                    ws.send(json.dumps({
                        "type": "error",
                        "message": f"Failed to process message: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }))
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")

def send_signal_to_clients(signal_data: Dict[str, Any]):
    """
    Add a signal to the queue to be sent to all connected clients.
    
    Args:
        signal_data: Signal data to be sent
    """
    signals_queue.put({
        "type": "signal",
        "data": signal_data,
        "timestamp": datetime.now().isoformat()
    })

def send_trade_update_to_clients(trade_data: Dict[str, Any]):
    """
    Add a trade update to the queue to be sent to all connected clients.
    
    Args:
        trade_data: Trade data to be sent
    """
    signals_queue.put({
        "type": "trade_update",
        "data": trade_data,
        "timestamp": datetime.now().isoformat()
    })