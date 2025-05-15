#!/usr/bin/env python3
"""
Create a scheduled task to monitor trades and trigger exits when needed.
This should be the missing link to activate your ExitNet system.
"""
import os
import time
import logging
from datetime import datetime
from app import app, db, Trade, TradeStatus
from position_manager import PositionManager, Position
from chart_utils import fetch_candles
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def monitor_trades_and_apply_exit_system():
    """
    Monitor open trades and run them through ExitNet to decide on exits.
    This should be scheduled to run regularly.
    """
    with app.app_context():
        # Get all open trades
        open_trades = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).all()
        logger.info(f"Found {len(open_trades)} open trades to evaluate")
        
        if not open_trades:
            logger.info("No open trades to process")
            return
        
        # Group trades by symbol to fetch price data once per symbol
        trades_by_symbol = {}
        for trade in open_trades:
            symbol = trade.symbol
            if symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = []
            trades_by_symbol[symbol].append(trade)
        
        # Create position manager
        pm = PositionManager()
        
        # Process trades by symbol
        for symbol, trades in trades_by_symbol.items():
            # Get latest market data for each symbol
            try:
                # Try to get H1 data first, fall back to M15 if not available
                candles = fetch_candles(symbol, timeframe="H1", count=10)
                timeframe = "H1"
                
                if not candles:
                    candles = fetch_candles(symbol, timeframe="M15", count=10)
                    timeframe = "M15"
                
                if not candles:
                    logger.warning(f"No price data available for {symbol}, skipping")
                    continue
                
                # Get latest price and high/low
                latest_candle = candles[-1]
                price = latest_candle['close']
                high = latest_candle['high']
                low = latest_candle['low']
                atr = high - low  # Simple approximation
                
                logger.info(f"Processing {len(trades)} trades for {symbol} at price {price}")
                
                # Add positions to manager
                for trade in trades:
                    # Only include trades with valid tickets
                    if not trade.ticket:
                        continue
                    
                    try:
                        # Create a position object for each trade
                        position = Position(
                            symbol=trade.symbol,
                            side=trade.side.value,
                            entry=trade.entry or price,
                            sl=trade.sl or (price * 0.98),  # Fallback SL at 2% if not set
                            tp=trade.tp or (price * 1.02),  # Fallback TP at 2% if not set
                            qty=trade.lot or 0.1,
                            open_time=time.time() - (86400 * 3),  # Assume open for a few days
                            ticket=int(trade.ticket),
                            bars_open=10,  # Assuming some bars have passed
                            context_tf=timeframe
                        )
                        
                        # Add to position manager
                        pm.positions.append(position)
                        
                    except Exception as e:
                        logger.error(f"Error creating position for trade {trade.id}: {e}")
                
                # Run the update which will evaluate exit conditions
                logger.info(f"Running exit evaluation for {len(pm.positions)} positions in {symbol}")
                pm.update_prices(price=price, high=high, low=low, atr=atr)
                
                # See if any trades were removed (exits triggered)
                exit_count = 0
                for trade in trades:
                    # Check if this trade's ticket is still in positions
                    if trade.ticket and not any(p.ticket == int(trade.ticket) for p in pm.positions):
                        exit_count += 1
                
                if exit_count > 0:
                    logger.info(f"ExitNet triggered {exit_count} exits for {symbol}")
                else:
                    logger.info(f"No exit signals triggered for {symbol}")
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
    
    logger.info("Trade monitoring completed")

if __name__ == "__main__":
    logger.info("Running trade exit monitor")
    monitor_trades_and_apply_exit_system()
    logger.info("Exit monitor job completed")