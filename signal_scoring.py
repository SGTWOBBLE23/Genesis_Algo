#!/usr/bin/env python3
"""
Signal Scoring Module

This module provides advanced signal filtering and scoring mechanisms to reduce excessive
trade entries and improve signal quality. It implements three scoring layers:

1. Technical Filter Layer: Additional scoring based on technical indicators
2. Performance-Based Adjustment: Dynamically adjusting confidence thresholds based on recent signal performance
3. Correlation Analysis: Avoiding multiple positions that are highly correlated
"""

import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union

from sqlalchemy import desc
from app import db, Signal, Trade, TradeStatus, SignalStatus, SignalAction, TradeSide

# Set up logging
logger = logging.getLogger(__name__)

class SignalScorer:
    """Implements advanced scoring and filtering for trading signals"""
    
    def __init__(self):
        # Configuration settings - can be moved to database settings later
        self.min_confidence_threshold = 0.65  # Base minimum confidence threshold
        self.max_signals_per_symbol = 2      # Maximum active signals per symbol
        self.max_signals_total = 5           # Maximum total active signals
        self.lookback_days = 14              # Performance lookback period
        self.correlated_pairs = {            # Pairs with high correlation
            'EUR_USD': ['GBP_USD'],
            'GBP_USD': ['EUR_USD'],
            'XAU_USD': [],                  # Gold often moves independently
            'USD_JPY': [],
            'GBP_JPY': ['EUR_JPY']
        }
        
    def apply_technical_filter(self, signal: Signal) -> float:
        """Apply technical analysis filters to evaluate the signal
        
        Args:
            signal: The signal to score
            
        Returns:
            float: Technical score adjustment (-0.1 to +0.1)
        """
        # Extract signal details
        symbol = signal.symbol
        action = signal.action
        confidence = signal.confidence
        
        # Default score adjustment
        score_adj = 0.0
        
        # Get context for additional signal data if available
        context = {}
        if hasattr(signal, 'context_json') and signal.context_json:
            try:
                context = json.loads(signal.context_json)
            except Exception as e:
                logger.warning(f"Error parsing signal context: {e}")
        
        # Technical filter 1: Check for RSI confirmation if available in context
        rsi = context.get('rsi', None)
        if rsi is not None:
            if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] and rsi < 30:
                # Oversold condition supporting buy signal
                score_adj += 0.05
            elif action in [SignalAction.SELL_NOW, SignalAction.ANTICIPATED_SHORT] and rsi > 70:
                # Overbought condition supporting sell signal
                score_adj += 0.05
            elif action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] and rsi > 70:
                # Overbought condition contradicting buy signal
                score_adj -= 0.05
            elif action in [SignalAction.SELL_NOW, SignalAction.ANTICIPATED_SHORT] and rsi < 30:
                # Oversold condition contradicting sell signal
                score_adj -= 0.05
        
        # Technical filter 2: Check for MACD confirmation
        macd = context.get('macd', None)
        macd_signal = context.get('macd_signal', None)
        if macd is not None and macd_signal is not None:
            if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] and macd > macd_signal:
                # MACD bullish crossover supporting buy signal
                score_adj += 0.05
            elif action in [SignalAction.SELL_NOW, SignalAction.ANTICIPATED_SHORT] and macd < macd_signal:
                # MACD bearish crossover supporting sell signal
                score_adj += 0.05
        
        # Cap the adjustment to -0.1 to +0.1 range
        return max(-0.1, min(0.1, score_adj))
    
    def apply_performance_adjustment(self, symbol: str, action: SignalAction) -> float:
        """Apply performance-based adjustment based on recent trading history
        
        Args:
            symbol: The trading symbol
            action: The signal action type
            
        Returns:
            float: Performance score adjustment (-0.1 to +0.1)
        """
        # Default score adjustment
        score_adj = 0.0
        
        try:
            # Calculate lookback period
            lookback_date = datetime.now() - timedelta(days=self.lookback_days)
            
            # Get recent trades for this symbol
            trades = db.session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == TradeStatus.CLOSED,
                Trade.closed_at >= lookback_date
            ).all()
            
            if not trades:
                return 0.0  # No recent trading history
            
            # Calculate win rate
            profitable_trades = sum(1 for trade in trades if trade.pnl and trade.pnl > 0)
            win_rate = profitable_trades / len(trades) if trades else 0
            
            # Convert action to side for comparison
            side = TradeSide.BUY if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] else TradeSide.SELL
            
            # Calculate direction-specific performance
            direction_trades = [t for t in trades if t.side == side]
            if direction_trades:
                direction_profitable = sum(1 for t in direction_trades if t.pnl and t.pnl > 0)
                direction_win_rate = direction_profitable / len(direction_trades)
                
                # Adjust score based on directional performance
                if direction_win_rate > 0.6:  # Good performance
                    score_adj += 0.05
                elif direction_win_rate < 0.4:  # Poor performance
                    score_adj -= 0.05
            
            # Overall performance adjustment
            if win_rate > 0.6:  # Good overall performance
                score_adj += 0.05
            elif win_rate < 0.4:  # Poor overall performance
                score_adj -= 0.05
                
        except Exception as e:
            logger.error(f"Error in performance adjustment: {e}")
            return 0.0
            
        # Cap the adjustment to -0.1 to +0.1 range
        return max(-0.1, min(0.1, score_adj))
    
    def check_correlation_conflict(self, symbol: str) -> bool:
        """Check if there's a correlation conflict with existing active positions
        
        Args:
            symbol: The trading symbol to check
            
        Returns:
            bool: True if there's a correlation conflict, False otherwise
        """
        try:
            # Get currently active signals
            active_signals = db.session.query(Signal).filter(
                Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE, SignalStatus.TRIGGERED])
            ).all()
            
            active_symbols = [s.symbol for s in active_signals]
            
            # Check if this symbol is already active
            symbol_count = active_symbols.count(symbol)
            if symbol_count >= self.max_signals_per_symbol:
                logger.info(f"Too many active signals for {symbol}: {symbol_count}")
                return True
                
            # Check for correlated symbols
            correlated_symbols = self.correlated_pairs.get(symbol, [])
            for corr_symbol in correlated_symbols:
                if corr_symbol in active_symbols:
                    logger.info(f"Correlation conflict: {symbol} is correlated with active {corr_symbol}")
                    return True
                    
            # Check total number of active signals
            if len(active_signals) >= self.max_signals_total:
                logger.info(f"Too many total active signals: {len(active_signals)}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error in correlation check: {e}")
            return False  # Default to allowing the signal in case of error
    
    def score_signal(self, signal: Signal) -> Tuple[float, bool]:
        """Apply all scoring layers to a signal and determine if it should be executed
        
        Args:
            signal: The signal to score
            
        Returns:
            Tuple[float, bool]: (final_score, should_execute)
        """
        symbol = signal.symbol
        action = signal.action
        base_confidence = signal.confidence
        
        # 1. Apply technical filter layer
        technical_adj = self.apply_technical_filter(signal)
        
        # 2. Apply performance-based adjustment
        performance_adj = self.apply_performance_adjustment(symbol, action)
        
        # 3. Check for correlation conflicts
        has_correlation_conflict = self.check_correlation_conflict(symbol)
        
        # Calculate final score
        final_score = base_confidence + technical_adj + performance_adj
        
        # Exceptional override: allow extremely high confidence signals to bypass correlation check
        override_correlation = final_score >= 0.95
        
        # Log correlation override if applicable
        if has_correlation_conflict and override_correlation:
            logger.info(f"High confidence signal ({final_score:.2f}) overriding correlation check")
        
        # Decision logic
        should_execute = (
            final_score >= self.min_confidence_threshold and 
            (not has_correlation_conflict or override_correlation)
        )
        
        # Log scoring results
        logger.info(f"Signal {signal.id} scoring results:")
        logger.info(f"  - Base confidence: {base_confidence:.2f}")
        logger.info(f"  - Technical adjustment: {technical_adj:.2f}")
        logger.info(f"  - Performance adjustment: {performance_adj:.2f}")
        logger.info(f"  - Correlation conflict: {has_correlation_conflict}")
        logger.info(f"  - Final score: {final_score:.2f}")
        logger.info(f"  - Override correlation: {override_correlation}")
        logger.info(f"  - Decision: {'EXECUTE' if should_execute else 'REJECT'}")

        
        return (final_score, should_execute)
    
    def filter_signals(self, signals: List[Signal]) -> List[Signal]:
        """Filter a list of signals based on scoring criteria
        
        Args:
            signals: List of signals to filter
            
        Returns:
            List[Signal]: Filtered list of signals that should be executed
        """
        if not signals:
            return []
            
        approved_signals = []
        
        for signal in signals:
            final_score, should_execute = self.score_signal(signal)
            
            # Update the signal's context with scoring information
            try:
                context = json.loads(signal.context_json) if signal.context_json else {}
                context['scoring'] = {
                    'final_score': round(final_score, 2),
                    'approved': should_execute,
                    'scored_at': datetime.now().isoformat()
                }
                signal.context_json = json.dumps(context)
                
                # Add to approved list if it passed all criteria
                if should_execute:
                    approved_signals.append(signal)
                    
            except Exception as e:
                logger.error(f"Error updating signal context: {e}")
        
        # Commit changes to the database
        db.session.commit()
        
        logger.info(f"Signal filtering complete: {len(approved_signals)}/{len(signals)} signals approved")
        return approved_signals

# Create a singleton instance for use throughout the application
signal_scorer = SignalScorer()
