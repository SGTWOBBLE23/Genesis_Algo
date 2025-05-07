#!/usr/bin/env python3

"""
Signal Scoring Module

This module provides advanced scoring and filtering mechanisms for trading signals.
It implements three key scoring layers:
1. Technical Filter Layer - Analyzes technical indicators and price patterns
2. Performance-Based Adjustment - Adjusts confidence thresholds based on past performance
3. Correlation Analysis - Prevents multiple positions in highly correlated pairs
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from app import db, Signal, Trade, SignalAction, SignalStatus, TradeStatus, TradeSide, Log, LogLevel
from chart_utils import fetch_candles
from sqlalchemy import text
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalScorer:
    """Signal scoring system to filter trading signals through multiple layers of validation"""
    
    def __init__(self):
        # Configuration settings
        self.min_confidence_threshold = 0.65  # Base minimum confidence threshold
        self.min_technical_score = 0.60      # Minimum technical score required
        self.max_correlation_threshold = 0.75 # Maximum correlation allowed between pairs
        self.evaluation_period_days = 14     # Days of history to analyze for performance adjustment
        
        # Currency correlations - initial estimates, will be dynamically updated
        self.pair_correlations = {
            'EURUSD': {
                'GBPUSD': 0.85,  # EUR and GBP often move together against USD
                'USDJPY': -0.65,  # EUR/USD and USD/JPY often move in opposite directions
                'GBPJPY': 0.35,   # Moderate correlation
                'XAUUSD': 0.45    # Moderate correlation with gold
            },
            'GBPUSD': {
                'EURUSD': 0.85,    # GBP and EUR often move together against USD
                'USDJPY': -0.60,   # Negative correlation
                'GBPJPY': 0.55,    # Moderate correlation
                'XAUUSD': 0.40     # Moderate correlation with gold
            },
            'USDJPY': {
                'EURUSD': -0.65,    # Negative correlation
                'GBPUSD': -0.60,    # Negative correlation
                'GBPJPY': 0.60,     # Positive correlation
                'XAUUSD': -0.35     # Weak negative correlation with gold
            },
            'GBPJPY': {
                'EURUSD': 0.35,     # Weak correlation
                'GBPUSD': 0.55,     # Moderate correlation
                'USDJPY': 0.60,     # Moderate correlation
                'XAUUSD': 0.20      # Weak correlation with gold
            },
            'XAUUSD': {
                'EURUSD': 0.45,     # Moderate correlation
                'GBPUSD': 0.40,     # Moderate correlation
                'USDJPY': -0.35,    # Weak negative correlation
                'GBPJPY': 0.20      # Weak correlation
            }
        }
        
        # Trade side mapping
        self.action_to_side = {
            SignalAction.BUY_NOW: TradeSide.BUY,
            SignalAction.SELL_NOW: TradeSide.SELL,
            SignalAction.ANTICIPATED_LONG: TradeSide.BUY,
            SignalAction.ANTICIPATED_SHORT: TradeSide.SELL
        }
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).fillna(0)
        loss = -delta.where(delta < 0, 0).fillna(0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # Default to neutral 50 for insufficient data
    
    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD line, signal line, and histogram"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_ema(self, prices, period):
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def evaluate_technical_conditions(self, symbol: str, action: SignalAction, 
                                     entry_price: float = None) -> Tuple[float, Dict]:
        """Evaluate technical conditions for the symbol and proposed action
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            action: Signal action (BUY_NOW, SELL_NOW, etc.)
            entry_price: Optional entry price for validation
            
        Returns:
            Tuple of (technical_score, details_dict)
        """
        try:
            # Get necessary OANDA format
            oanda_symbol = symbol
            if '_' not in symbol:
                # Convert MT5 format to OANDA format (e.g., EURUSD to EUR_USD)
                oanda_symbol = re.sub(r'([A-Z]{3})([A-Z]{3})', r'\1_\2', symbol)
            
            # Fetch candle data
            candles = fetch_candles(oanda_symbol, timeframe="H1", count=100)
            if not candles:
                logger.warning(f"No candle data available for {symbol}, using default score")
                return 0.5, {"error": "No candle data available"}
            
            # Convert to pandas DataFrame
            df = pd.DataFrame([
                {
                    'time': candle['time'],
                    'open': float(candle['mid']['o']),
                    'high': float(candle['mid']['h']),
                    'low': float(candle['mid']['l']),
                    'close': float(candle['mid']['c']),
                    'volume': float(candle['volume']) if 'volume' in candle else 0
                } for candle in candles
            ])
            
            if df.empty:
                logger.warning(f"Empty DataFrame for {symbol}, using default score")
                return 0.5, {"error": "Empty price data"}
            
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            # Calculate technical indicators
            df['rsi'] = self._calculate_rsi(df['close'])
            df['macd'], df['signal'], df['histogram'] = self._calculate_macd(df['close'])
            df['ema20'] = self._calculate_ema(df['close'], 20)
            df['ema50'] = self._calculate_ema(df['close'], 50)
            df['ema200'] = self._calculate_ema(df['close'], 200)
            
            # Prepare scores for different technical aspects
            scores = {}
            details = {}
            
            # Get latest values
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Store current technical levels
            details["current_price"] = float(latest['close'])
            details["rsi"] = float(latest['rsi'])
            details["macd"] = float(latest['macd'])
            details["signal"] = float(latest['signal'])
            details["ema20"] = float(latest['ema20'])
            details["ema50"] = float(latest['ema50'])
            details["ema200"] = float(latest['ema200'])
            
            # 1. RSI conditions
            if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG]:
                # For buy signals, prefer RSI not overbought and preferably rising from oversold
                if latest['rsi'] < 30:  # Oversold condition
                    scores['rsi'] = 1.0
                    details["rsi_evaluation"] = "oversold"
                elif 30 <= latest['rsi'] < 50:  # Rising from oversold
                    scores['rsi'] = 0.8
                    details["rsi_evaluation"] = "rising_from_oversold"
                elif 50 <= latest['rsi'] < 70:  # Neutral to bullish
                    scores['rsi'] = 0.6
                    details["rsi_evaluation"] = "neutral_to_bullish"
                else:  # Overbought
                    scores['rsi'] = 0.3
                    details["rsi_evaluation"] = "overbought"
            else:  # SELL signals
                # For sell signals, prefer RSI not oversold and preferably falling from overbought
                if latest['rsi'] > 70:  # Overbought condition
                    scores['rsi'] = 1.0
                    details["rsi_evaluation"] = "overbought"
                elif 50 < latest['rsi'] <= 70:  # Falling from overbought
                    scores['rsi'] = 0.8
                    details["rsi_evaluation"] = "falling_from_overbought"
                elif 30 < latest['rsi'] <= 50:  # Neutral to bearish
                    scores['rsi'] = 0.6
                    details["rsi_evaluation"] = "neutral_to_bearish"
                else:  # Oversold
                    scores['rsi'] = 0.3
                    details["rsi_evaluation"] = "oversold"
            
            # 2. MACD conditions
            macd_crossover = (prev['macd'] < prev['signal'] and latest['macd'] > latest['signal'])  # Bullish crossover
            macd_crossunder = (prev['macd'] > prev['signal'] and latest['macd'] < latest['signal'])  # Bearish crossover
            
            if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG]:
                if macd_crossover:
                    scores['macd'] = 1.0
                    details["macd_evaluation"] = "bullish_crossover"
                elif latest['macd'] > latest['signal']:
                    scores['macd'] = 0.8
                    details["macd_evaluation"] = "bullish_momentum"
                elif latest['macd'] < 0 and latest['histogram'] > prev['histogram']:  # Improving while below zero
                    scores['macd'] = 0.6
                    details["macd_evaluation"] = "improving_below_zero"
                else:
                    scores['macd'] = 0.4
                    details["macd_evaluation"] = "bearish_momentum"
            else:  # SELL signals
                if macd_crossunder:
                    scores['macd'] = 1.0
                    details["macd_evaluation"] = "bearish_crossover"
                elif latest['macd'] < latest['signal']:
                    scores['macd'] = 0.8
                    details["macd_evaluation"] = "bearish_momentum"
                elif latest['macd'] > 0 and latest['histogram'] < prev['histogram']:  # Deteriorating while above zero
                    scores['macd'] = 0.6
                    details["macd_evaluation"] = "deteriorating_above_zero"
                else:
                    scores['macd'] = 0.4
                    details["macd_evaluation"] = "bullish_momentum"
            
            # 3. Trend following (EMA conditions)
            if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG]:
                # For buys, price above EMAs is bullish
                if latest['close'] > latest['ema20'] > latest['ema50'] > latest['ema200']:
                    scores['trend'] = 1.0
                    details["trend_evaluation"] = "strong_uptrend"
                elif latest['close'] > latest['ema20'] and latest['ema20'] > latest['ema50']:
                    scores['trend'] = 0.8
                    details["trend_evaluation"] = "moderate_uptrend"
                elif latest['close'] > latest['ema20']:
                    scores['trend'] = 0.6
                    details["trend_evaluation"] = "weak_uptrend"
                else:
                    scores['trend'] = 0.3
                    details["trend_evaluation"] = "downtrend"
            else:  # SELL signals
                # For sells, price below EMAs is bearish
                if latest['close'] < latest['ema20'] < latest['ema50'] < latest['ema200']:
                    scores['trend'] = 1.0
                    details["trend_evaluation"] = "strong_downtrend"
                elif latest['close'] < latest['ema20'] and latest['ema20'] < latest['ema50']:
                    scores['trend'] = 0.8
                    details["trend_evaluation"] = "moderate_downtrend"
                elif latest['close'] < latest['ema20']:
                    scores['trend'] = 0.6
                    details["trend_evaluation"] = "weak_downtrend"
                else:
                    scores['trend'] = 0.3
                    details["trend_evaluation"] = "uptrend"
            
            # 4. Entry price validation (if provided)
            if entry_price is not None:
                # Check if entry price is reasonable compared to current price
                current_price = latest['close']
                price_diff_pct = abs(entry_price - current_price) / current_price
                
                if price_diff_pct < 0.001:  # Very close to current price (< 0.1%)
                    scores['entry_price'] = 1.0
                    details["entry_price_evaluation"] = "excellent"
                elif price_diff_pct < 0.005:  # Within 0.5% of current price
                    scores['entry_price'] = 0.8
                    details["entry_price_evaluation"] = "good"
                elif price_diff_pct < 0.01:  # Within 1% of current price
                    scores['entry_price'] = 0.6
                    details["entry_price_evaluation"] = "acceptable"
                else:  # More than 1% away
                    scores['entry_price'] = 0.2
                    details["entry_price_evaluation"] = "poor"
            
            # Calculate final technical score with weightings
            if len(scores) > 0:
                weights = {
                    'rsi': 0.25,
                    'macd': 0.30,
                    'trend': 0.35,
                    'entry_price': 0.10  # Lower weight since not always available
                }
                
                # Normalize weights based on available scores
                available_weights = {k: v for k, v in weights.items() if k in scores}
                total_weight = sum(available_weights.values())
                normalized_weights = {k: v/total_weight for k, v in available_weights.items()}
                
                # Calculate weighted score
                technical_score = sum(scores[k] * normalized_weights[k] for k in scores)
                details["component_scores"] = scores
                details["final_technical_score"] = technical_score
                return technical_score, details
            else:
                logger.warning(f"No technical scores calculated for {symbol}, using default")
                return 0.5, {"error": "No technical scores calculated"}
                
        except Exception as e:
            logger.error(f"Error in technical evaluation: {str(e)}")
            return 0.5, {"error": str(e)}  # Default to neutral score on error
    
    def evaluate_performance_adjustment(self, symbol: str, action: SignalAction) -> Tuple[float, Dict]:
        """Evaluate past performance to adjust confidence threshold
        
        Args:
            symbol: Trading symbol
            action: Signal action
            
        Returns:
            Tuple of (adjustment_factor, details_dict)
            - adjustment_factor: Value between 0.7 and 1.3 to multiply confidence threshold
              (>1 means require higher confidence, <1 means allow lower confidence)
        """
        try:
            # Map signal action to trade side
            side = self.action_to_side.get(action)
            if not side:
                logger.warning(f"Unknown action type {action}, using default adjustment")
                return 1.0, {"error": "Unknown action type"}
            
            # Get performance data from recent trades
            cutoff_date = datetime.now() - timedelta(days=self.evaluation_period_days)
            
            trades = Trade.query.filter(
                Trade.symbol == symbol,
                Trade.side == side,
                Trade.status == TradeStatus.CLOSED,
                Trade.closed_at >= cutoff_date
            ).all()
            
            if not trades:
                logger.info(f"No recent trade history for {symbol} {side.name}, using default adjustment")
                return 1.0, {"reason": "No recent trade history"}
            
            # Calculate performance metrics
            total_trades = len(trades)
            profitable_trades = sum(1 for t in trades if t.pnl and t.pnl > 0)
            
            if total_trades == 0:
                return 1.0, {"reason": "No trades to analyze"}
            
            win_rate = profitable_trades / total_trades
            total_profit = sum(t.pnl if t.pnl else 0 for t in trades)
            avg_profit = total_profit / total_trades
            
            details = {
                "total_trades": total_trades,
                "profitable_trades": profitable_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "avg_profit": avg_profit,
            }
            
            # Determine adjustment factor based on performance
            # Higher win rate -> Lower threshold (more permissive)
            # Lower win rate -> Higher threshold (more restrictive)
            if win_rate >= 0.7:  # Excellent performance
                adjustment_factor = 0.7  # Reduce threshold by 30%
                details["evaluation"] = "excellent"
            elif win_rate >= 0.5:  # Good performance
                adjustment_factor = 0.9  # Reduce threshold by 10%
                details["evaluation"] = "good"
            elif win_rate >= 0.4:  # Acceptable performance
                adjustment_factor = 1.0  # No adjustment
                details["evaluation"] = "acceptable"
            elif win_rate >= 0.3:  # Poor performance
                adjustment_factor = 1.1  # Increase threshold by 10%
                details["evaluation"] = "poor"
            else:  # Very poor performance
                adjustment_factor = 1.3  # Increase threshold by 30%
                details["evaluation"] = "very_poor"
                
            # Consider profitability as well
            if avg_profit > 0 and adjustment_factor > 0.8:
                adjustment_factor -= 0.1  # Slightly more permissive for profitable strategies
                details["profit_bonus"] = True
            elif avg_profit < 0 and adjustment_factor < 1.2:
                adjustment_factor += 0.1  # Slightly more restrictive for unprofitable strategies
                details["profit_penalty"] = True
                
            details["final_adjustment_factor"] = adjustment_factor
            return adjustment_factor, details
            
        except Exception as e:
            logger.error(f"Error in performance evaluation: {str(e)}")
            return 1.0, {"error": str(e)}  # No adjustment on error
    
    def evaluate_correlation(self, symbol: str, action: SignalAction) -> Tuple[bool, Dict]:
        """Evaluate correlation with existing positions
        
        Args:
            symbol: Trading symbol
            action: Signal action
            
        Returns:
            Tuple of (should_proceed, details_dict)
            - should_proceed: True if correlation check passes, False if failed
        """
        try:
            # Get current open positions
            open_trades = Trade.query.filter(Trade.status == TradeStatus.OPEN).all()
            
            if not open_trades:
                # No open trades, correlation check automatically passes
                return True, {"reason": "No open trades"}
            
            # Map signal action to trade side
            side = self.action_to_side.get(action)
            if not side:
                logger.warning(f"Unknown action type {action}, allowing trade")
                return True, {"error": "Unknown action type"}
            
            # Check correlation with each open position
            correlations = []
            for trade in open_trades:
                trade_symbol = trade.symbol
                trade_side = trade.side
                
                # Skip same symbol - handled by risk management
                if trade_symbol == symbol:
                    continue
                
                # Get base correlation
                if trade_symbol in self.pair_correlations and symbol in self.pair_correlations[trade_symbol]:
                    base_correlation = self.pair_correlations[trade_symbol][symbol]
                elif symbol in self.pair_correlations and trade_symbol in self.pair_correlations[symbol]:
                    base_correlation = self.pair_correlations[symbol][trade_symbol]
                else:
                    # Unknown correlation, assume moderate
                    base_correlation = 0.5
                
                # Adjust for trade direction
                # If same direction, correlation remains the same
                # If opposite direction, invert correlation
                effective_correlation = base_correlation
                if trade_side != side:
                    effective_correlation = -effective_correlation
                
                correlations.append({
                    "symbol": trade_symbol,
                    "side": trade_side.name,
                    "base_correlation": base_correlation,
                    "effective_correlation": effective_correlation
                })
            
            # Check if any high correlations exist
            high_correlations = [c for c in correlations if abs(c["effective_correlation"]) >= self.max_correlation_threshold]
            
            details = {
                "proposed_trade": {
                    "symbol": symbol,
                    "side": side.name
                },
                "existing_positions": len(open_trades),
                "correlations": correlations,
                "high_correlations": high_correlations
            }
            
            if high_correlations:
                details["passed"] = False
                details["reason"] = "High correlation with existing positions"
                return False, details
            else:
                details["passed"] = True
                details["reason"] = "Acceptable correlation with existing positions"
                return True, details
            
        except Exception as e:
            logger.error(f"Error in correlation evaluation: {str(e)}")
            return True, {"error": str(e)}  # Allow trade on error
    
    def should_execute_signal(self, signal: Signal) -> Tuple[bool, Dict]:
        """Evaluate whether a signal should be executed based on all scoring layers
        
        Args:
            signal: The Signal object to evaluate
            
        Returns:
            Tuple of (should_execute, details_dict)
        """
        try:
            result = {"signal_id": signal.id, "symbol": signal.symbol, "action": signal.action.name}
            
            # Step 1: Technical Filter Layer
            technical_score, technical_details = self.evaluate_technical_conditions(
                symbol=signal.symbol, 
                action=signal.action,
                entry_price=signal.entry
            )
            result["technical_score"] = technical_score
            result["technical_details"] = technical_details
            
            if technical_score < self.min_technical_score:
                result["decision"] = "reject"
                result["reason"] = f"Technical score {technical_score:.2f} below threshold {self.min_technical_score:.2f}"
                return False, result
            
            # Step 2: Performance-Based Adjustment
            adjustment_factor, performance_details = self.evaluate_performance_adjustment(
                symbol=signal.symbol,
                action=signal.action
            )
            result["adjustment_factor"] = adjustment_factor
            result["performance_details"] = performance_details
            
            # Apply adjustment to confidence threshold
            adjusted_threshold = min(0.95, max(0.5, self.min_confidence_threshold * adjustment_factor))
            result["base_confidence_threshold"] = self.min_confidence_threshold
            result["adjusted_confidence_threshold"] = adjusted_threshold
            
            if signal.confidence < adjusted_threshold:
                result["decision"] = "reject"
                result["reason"] = f"Signal confidence {signal.confidence:.2f} below adjusted threshold {adjusted_threshold:.2f}"
                return False, result
            
            # Step 3: Correlation Analysis
            correlation_passed, correlation_details = self.evaluate_correlation(
                symbol=signal.symbol,
                action=signal.action
            )
            result["correlation_passed"] = correlation_passed
            result["correlation_details"] = correlation_details
            
            if not correlation_passed:
                result["decision"] = "reject"
                result["reason"] = "Failed correlation check"
                return False, result
            
            # All checks passed
            result["decision"] = "execute"
            result["reason"] = "Passed all scoring layers"
            return True, result
            
        except Exception as e:
            logger.error(f"Error in signal scoring: {str(e)}")
            # On error, default to original confidence threshold
            error_result = {
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "action": signal.action.name,
                "error": str(e)
            }
            
            if signal.confidence >= self.min_confidence_threshold:
                error_result["decision"] = "execute"
                error_result["reason"] = "Error in scoring, defaulting to base confidence check"
                return True, error_result
            else:
                error_result["decision"] = "reject"
                error_result["reason"] = "Error in scoring and below base confidence threshold"
                return False, error_result

# Global instance
signal_scorer = SignalScorer()
