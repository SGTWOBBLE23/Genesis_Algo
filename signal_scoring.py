#!/usr/bin/env python3
"""
Signal-Scoring Module
─────────────────────
Provides advanced scoring and filtering for trading signals.  It implements
three layers:

1) Technical-filter layer            – indicator / pattern checks
2) Performance-based adjustment      – raises / lowers thresholds by recent P&L
3) Correlation guard                 – avoids stacking trades on correlated pairs
"""

# -- Python std-lib
import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
import re

# -- Third-party
import pandas as pd
import numpy as np
from sqlalchemy import text, and_

# -- Project sub-modules
from app import (
    db,                         # SQLAlchemy session
    Signal, Trade,
    SignalAction, SignalStatus,
    TradeStatus, TradeSide,
    Log, LogLevel,
)
from chart_utils import fetch_candles

# --------------------------------------------------------------------------
#  Configuration
# --------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).resolve().parent / "config" / "signal_weights.json"

# --------------------------------------------------------------------------
#  Logging
# --------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _WeightCache:
    def __init__(self):
        self._mtime   = 0
        self._weights = {}

    def get(self) -> Dict[str, float]:
        try:
            stat = CONFIG_PATH.stat()
            if stat.st_mtime > self._mtime:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                self._weights = data.get("factors", {})
                self._default = data.get("default_weight", 1.0)
                self._mtime   = stat.st_mtime
                logger.info(f"Reloaded weights (v{data.get(\"version\")})")
        except FileNotFoundError:
            logger.warning("Weight table missing; using defaults")
            self._weights, self._default = {}, 1.0
        return self._weights

    def weight(self, key: str) -> float:
        return self.get().get(key, self._default)

weight_cache = _WeightCache()

class SignalScorer:
    """Signal scoring system to filter trading signals through multiple layers of validation"""

    def __init__(self):
        """Initialize the SignalScorer with default settings"""
        # Configuration settings
        self.min_confidence_threshold = 0.70  # Base minimum confidence threshold
        self.min_technical_score = 0.60      # Minimum technical score required
        self.max_correlation_threshold = 0.75 # Maximum correlation allowed between pairs
        self.evaluation_period_days = 90     # Days of history to analyze for performance adjustment (extended from 14)
        
        # Trade side mapping
        self.action_to_side = {
            SignalAction.BUY_NOW: TradeSide.BUY,
            SignalAction.SELL_NOW: TradeSide.SELL,
            SignalAction.ANTICIPATED_LONG: TradeSide.BUY,
            SignalAction.ANTICIPATED_SHORT: TradeSide.SELL
        }
        
        # Currency correlations - initial estimates, will be dynamically updated
        self.pair_correlations = {
            "EURUSD": {
                "GBPUSD": 0.85,  # EUR and GBP often move together against USD
                "USDJPY": -0.65,  # EUR/USD and USD/JPY often move in opposite directions
                "GBPJPY": 0.35,   # Moderate correlation
                "XAUUSD": 0.45    # Moderate correlation with gold
            },
            "GBPUSD": {
                "EURUSD": 0.85,    # GBP and EUR often move together against USD
                "USDJPY": -0.60,   # Negative correlation
                "GBPJPY": 0.55,    # Moderate correlation
                "XAUUSD": 0.40     # Moderate correlation with gold
            },
            "USDJPY": {
                "EURUSD": -0.65,    # Negative correlation
                "GBPUSD": -0.60,    # Negative correlation
                "GBPJPY": 0.60,     # Positive correlation
                "XAUUSD": -0.35     # Weak negative correlation with gold
            },
            "GBPJPY": {
                "EURUSD": 0.35,     # Weak correlation
                "GBPUSD": 0.55,     # Moderate correlation
                "USDJPY": 0.60,     # Moderate correlation
                "XAUUSD": 0.20      # Weak correlation with gold
            },
            "XAUUSD": {
                "EURUSD": 0.45,     # Moderate correlation
                "GBPUSD": 0.40,     # Moderate correlation
                "USDJPY": -0.35,    # Weak negative correlation
                "GBPJPY": 0.20      # Weak correlation
            }
        }
    
    def _normalize_symbol_for_db(self, symbol: str) -> str:
        """Convert symbol with underscores (XAU_USD) to format stored in database (XAUUSD)"""
        return symbol.replace("_", "") if symbol else symbol

    def merge_or_update(self, signal: "Signal") -> bool:
        """
        If an open signal of the same symbol + action exists and the
        entry prices are within a small tolerance, roll this new evidence
        into the existing one instead of keeping a duplicate.

        Returns:
            True - We kept the new signal (no merge)
            False - We merged and deleted the newcomer
        """
        def _pip_tol(sym: str) -> float:
            if sym.startswith(("XAU", "XAG")):           # metals
                return 1.0                               # $1 = 10 pipettes
            if sym.endswith("JPY"):                      # 3-dp JPY pairs
                return 0.10                              # 0.10 = 10 pips
            return 0.001                                 # 0.0010 = 10 pips (4-dp FX)

        tol   = _pip_tol(signal.symbol)
        price = float(signal.entry or 0)

        # Look for the *latest* PENDING / ACTIVE sibling
        sibling = (
            db.session.query(Signal)
            .filter(
                Signal.id != signal.id,                       # not itself
                Signal.symbol == signal.symbol,
                Signal.action == signal.action,
                Signal.status.in_([
                    SignalStatus.PENDING.value,
                    SignalStatus.ACTIVE.value,
                    SignalStatus.TRIGGERED.value
                ])
            )
            .order_by(Signal.created_at.desc())
            .first()
        )

        if not sibling:
            return True   # nothing to merge with

        sib_price = float(sibling.entry or 0)

        if abs(price - sib_price) > tol:
            return True   # far enough apart → keep both

        # Combined confidence = 1 - product(1 - c_i)
        # (probabilistic union of independent confirmations)
        combined = 1 - (1 - sibling.confidence) * (1 - signal.confidence)
        sibling.confidence = round(combined, 4)

        # Append provenance for audit
        ctx = sibling.context
        merged = ctx.get("merged_ids", [])
        merged.append(signal.id)
        ctx["merged_ids"] = merged
        sibling.context = ctx

        # Soft-delete the newcomer (CANCELLED keeps the row for traceability)
        signal.status = SignalStatus.CANCELLED.value
        signal.context = {"reason": "merged_into", "target_id": sibling.id}

        db.session.commit()
        logger.info(
            f"Merged signal {signal.id} into {sibling.id}; "
            f"new confidence {sibling.confidence:.2f}"
        )
        return False
        
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

    def evaluate_technical_conditions(
        self,
        symbol: str,
        action: SignalAction,
        entry_price: float | None
    ) -> Tuple[float, Dict]:
        """
        Evaluate technical conditions for a symbol / action.

        Returns:
            (technical_score, details_dict)
        """
        try:
            # Normalize symbol format for OANDA
            oanda_symbol = symbol
            if '_' not in symbol:
                oanda_symbol = re.sub(r'([A-Z]{3})([A-Z]{3})', r'\1_\2', symbol)

            # Fetch last 100 H1 candles
            candles = fetch_candles(oanda_symbol, timeframe="H1", count=100)
            if not candles:
                logger.warning(f"No candle data for {symbol}")
                return 0.5, {"error": "no_candles"}

            df = pd.DataFrame(
                {
                    "time":      c.get("time", c["timestamp"]),   # safe access
                    "open":      c["open"],
                    "high":      c["high"],
                    "low":       c["low"],
                    "close":     c["close"],
                }
                for c in candles
            )

            if df.empty:
                logger.warning(f"Empty DataFrame for {symbol}")
                return 0.5, {"error": "empty_df"}

            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)

            # Calculate indicators
            df["rsi"]       = self._calculate_rsi(df["close"])
            df["macd"], df["signal"], df["histogram"] = self._calculate_macd(df["close"])
            df["ema20"]     = self._calculate_ema(df["close"], 20)
            df["ema50"]     = self._calculate_ema(df["close"], 50)
            df["ema200"]    = self._calculate_ema(df["close"], 200)

            latest = df.iloc[-1]
            prev   = df.iloc[-2] if len(df) > 1 else latest

            # Build factor-level scores
            scores = {}
            details = {
                "current_price": float(latest["close"]),
                "rsi":           float(latest["rsi"]),
                "macd":          float(latest["macd"]),
                "signal":        float(latest["signal"]),
                "ema20":         float(latest["ema20"]),
                "ema50":         float(latest["ema50"]),
                "ema200":        float(latest["ema200"]),
            }

            # RSI
            if action in (SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG):
                if latest["rsi"] < 30:
                    scores["rsi"] = 1.0;  details["rsi_evaluation"] = "oversold"
                elif 30 <= latest["rsi"] < 50:
                    scores["rsi"] = 0.8;  details["rsi_evaluation"] = "rising_from_oversold"
                elif 50 <= latest["rsi"] < 70:
                    scores["rsi"] = 0.6;  details["rsi_evaluation"] = "neutral_to_bullish"
                else:
                    scores["rsi"] = 0.3;  details["rsi_evaluation"] = "overbought"
            else:
                if latest["rsi"] > 70:
                    scores["rsi"] = 1.0;  details["rsi_evaluation"] = "overbought"
                elif 50 < latest["rsi"] <= 70:
                    scores["rsi"] = 0.8;  details["rsi_evaluation"] = "falling_from_overbought"
                elif 30 < latest["rsi"] <= 50:
                    scores["rsi"] = 0.6;  details["rsi_evaluation"] = "neutral_to_bearish"
                else:
                    scores["rsi"] = 0.3;  details["rsi_evaluation"] = "oversold"

            # MACD
            macd_cross = prev["macd"] < prev["signal"] < latest["macd"] > latest["signal"]
            macd_under = prev["macd"] > prev["signal"] > latest["macd"] < latest["signal"]

            if action in (SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG):
                if macd_cross:
                    scores["macd"] = 1.0; details["macd_evaluation"] = "bullish_crossover"
                elif latest["macd"] > latest["signal"]:
                    scores["macd"] = 0.8; details["macd_evaluation"] = "bullish_momentum"
                elif latest["macd"] < 0 and latest["histogram"] > prev["histogram"]:
                    scores["macd"] = 0.6; details["macd_evaluation"] = "improving_below_zero"
                else:
                    scores["macd"] = 0.4; details["macd_evaluation"] = "bearish_momentum"
            else:
                if macd_under:
                    scores["macd"] = 1.0; details["macd_evaluation"] = "bearish_crossover"
                elif latest["macd"] < latest["signal"]:
                    scores["macd"] = 0.8; details["macd_evaluation"] = "bearish_momentum"
                elif latest["macd"] > 0 and latest["histogram"] < prev["histogram"]:
                    scores["macd"] = 0.6; details["macd_evaluation"] = "deteriorating_above_zero"
                else:
                    scores["macd"] = 0.4; details["macd_evaluation"] = "bullish_momentum"

            # Trend (EMA stack)
            if action in (SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG):
                if latest["close"] > latest["ema20"] > latest["ema50"] > latest["ema200"]:
                    scores["trend"] = 1.0; details["trend_evaluation"] = "strong_uptrend"
                elif latest["close"] > latest["ema20"] > latest["ema50"]:
                    scores["trend"] = 0.8; details["trend_evaluation"] = "moderate_uptrend"
                elif latest["close"] > latest["ema20"]:
                    scores["trend"] = 0.6; details["trend_evaluation"] = "weak_uptrend"
                else:
                    scores["trend"] = 0.3; details["trend_evaluation"] = "downtrend"
            else:
                if latest["close"] < latest["ema20"] < latest["ema50"] < latest["ema200"]:
                    scores["trend"] = 1.0; details["trend_evaluation"] = "strong_downtrend"
                elif latest["close"] < latest["ema20"] < latest["ema50"]:
                    scores["trend"] = 0.8; details["trend_evaluation"] = "moderate_downtrend"
                elif latest["close"] < latest["ema20"]:
                    scores["trend"] = 0.6; details["trend_evaluation"] = "weak_downtrend"
                else:
                    scores["trend"] = 0.3; details["trend_evaluation"] = "uptrend"

            # Entry-price sanity check
            if entry_price is not None:
                diff = abs(entry_price - latest["close"]) / latest["close"]
                if diff < 0.001:
                    scores["entry_price"] = 1.0; details["entry_price_evaluation"] = "excellent"
                elif diff < 0.005:
                    scores["entry_price"] = 0.8; details["entry_price_evaluation"] = "good"
                elif diff < 0.01:
                    scores["entry_price"] = 0.6; details["entry_price_evaluation"] = "fair"
                else:
                    scores["entry_price"] = 0.4; details["entry_price_evaluation"] = "poor"

            # Support / Resistance
            # Simplified check - is price near recent high/low?
            recent_high = df["high"][-20:].max()
            recent_low = df["low"][-20:].min()
            price_range = recent_high - recent_low
            
            if price_range > 0:
                if action in (SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG):
                    # Buy near support
                    proximity_to_low = (latest["close"] - recent_low) / price_range
                    if proximity_to_low < 0.2:
                        scores["support_resistance"] = 1.0
                        details["support_resistance_eval"] = "near_support"
                    elif proximity_to_low < 0.4:
                        scores["support_resistance"] = 0.7
                        details["support_resistance_eval"] = "above_support"
                    else:
                        scores["support_resistance"] = 0.4
                        details["support_resistance_eval"] = "far_from_support"
                else:
                    # Sell near resistance
                    proximity_to_high = (recent_high - latest["close"]) / price_range
                    if proximity_to_high < 0.2:
                        scores["support_resistance"] = 1.0
                        details["support_resistance_eval"] = "near_resistance"
                    elif proximity_to_high < 0.4:
                        scores["support_resistance"] = 0.7
                        details["support_resistance_eval"] = "below_resistance"
                    else:
                        scores["support_resistance"] = 0.4
                        details["support_resistance_eval"] = "far_from_resistance"

            # Calculate the weighted average of all scores
            total_weight = 0
            weighted_sum = 0
            
            for factor, score in scores.items():
                weight = weight_cache.weight(factor)
                weighted_sum += score * weight
                total_weight += weight
                
                details[f"{factor}_weight"] = weight
                details[f"{factor}_score"] = score
            
            if total_weight > 0:
                technical_score = round(weighted_sum / total_weight, 2)
            else:
                technical_score = 0.5  # Neutral if no factors found
                
            details["technical_score"] = technical_score
            details["score_factors"] = list(scores.keys())
            
            return technical_score, details
            
        except Exception as e:
            logger.error(f"Error in technical evaluation: {str(e)}", exc_info=True)
            return 0.5, {"error": str(e)}  # Return neutral score on error

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
            # Convert symbol to XAUUSD format if needed
            db_symbol = self._normalize_symbol_for_db(symbol)
            side = self.action_to_side.get(action, TradeSide.BUY)
            
            # Get closed trades for this symbol and side in the evaluation period
            cutoff_date = datetime.now() - timedelta(days=self.evaluation_period_days)
            trades = (
                db.session.query(Trade)
                .filter(
                    Trade.symbol == db_symbol,
                    Trade.side == side,
                    Trade.status == TradeStatus.CLOSED,
                    Trade.closed_at >= cutoff_date
                )
                .all()
            )
            
            if not trades:
                return 1.0, {"reason": "no_history"}
                
            # Calculate win rate and average profit/loss
            total_trades = len(trades)
            win_trades = sum(1 for t in trades if t.pnl is not None and t.pnl > 0)
            loss_trades = sum(1 for t in trades if t.pnl is not None and t.pnl < 0)
            
            if total_trades == 0:
                return 1.0, {"reason": "no_valid_trades"}
                
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            
            # Calculate adjustment factor
            if win_rate >= 0.7:
                # Very good performance - relax threshold
                adjustment = 0.8
                reason = "excellent_performance"
            elif win_rate >= 0.55:
                # Good performance - slightly relax threshold
                adjustment = 0.9
                reason = "good_performance"
            elif win_rate >= 0.45:
                # Average performance - neutral
                adjustment = 1.0
                reason = "average_performance"
            elif win_rate >= 0.3:
                # Below average - increase threshold
                adjustment = 1.1
                reason = "below_average_performance"
            else:
                # Poor performance - significantly increase threshold
                adjustment = 1.2
                reason = "poor_performance"
                
            details = {
                "win_rate": win_rate,
                "total_trades": total_trades,
                "winning_trades": win_trades,
                "losing_trades": loss_trades,
                "evaluation_period_days": self.evaluation_period_days,
                "reason": reason,
                "adjustment_factor": adjustment
            }
            
            return adjustment, details
            
        except Exception as e:
            logger.error(f"Error in performance evaluation: {str(e)}", exc_info=True)
            return 1.0, {"error": str(e)}  # Return neutral adjustment on error
            
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
            # Convert symbol to XAUUSD format for DB queries
            db_symbol = self._normalize_symbol_for_db(symbol)
            side = self.action_to_side.get(action, TradeSide.BUY)
            
            # Get open trades for all symbols
            open_trades = (
                db.session.query(Trade)
                .filter(
                    Trade.status == TradeStatus.OPEN
                )
                .all()
            )
            
            if not open_trades:
                return True, {"reason": "no_open_positions"}
                
            # Check correlation with each open position
            correlated_positions = []
            for trade in open_trades:
                # Skip same symbol
                if trade.symbol == db_symbol:
                    continue
                    
                # Get correlation coefficient if defined
                correlation = 0
                if db_symbol in self.pair_correlations and trade.symbol in self.pair_correlations[db_symbol]:
                    correlation = self.pair_correlations[db_symbol][trade.symbol]
                elif trade.symbol in self.pair_correlations and db_symbol in self.pair_correlations[trade.symbol]:
                    correlation = self.pair_correlations[trade.symbol][db_symbol]
                
                # For positions in the same direction, high positive correlation is a concern
                # For opposite directions, high negative correlation is a concern
                same_direction = (trade.side == side)
                if same_direction and correlation > self.max_correlation_threshold:
                    correlated_positions.append({
                        "symbol": trade.symbol,
                        "correlation": correlation,
                        "direction": "same"
                    })
                elif not same_direction and correlation < -self.max_correlation_threshold:
                    correlated_positions.append({
                        "symbol": trade.symbol,
                        "correlation": correlation,
                        "direction": "opposite"
                    })
            
            # Decide based on correlated positions
            should_proceed = len(correlated_positions) == 0
            
            details = {
                "should_proceed": should_proceed,
                "open_positions": len(open_trades),
                "correlated_positions": correlated_positions,
                "max_correlation_threshold": self.max_correlation_threshold
            }
            
            return should_proceed, details
            
        except Exception as e:
            logger.error(f"Error in correlation evaluation: {str(e)}", exc_info=True)
            return True, {"error": str(e)}  # Allow signal on error (safer)

    def should_execute_signal(self, signal: Signal) -> Tuple[bool, Dict]:
        """Evaluate whether a signal should be executed based on all scoring layers

        Args:
            signal: The Signal object to evaluate

        Returns:
            Tuple of (should_execute, details_dict)
        """
        result = {"layers": {}}
        
        # Layer 1: Technical conditions
        technical_score, tech_details = self.evaluate_technical_conditions(
            signal.symbol, signal.action, signal.entry
        )
        result["layers"]["technical"] = tech_details
        
        if technical_score < self.min_technical_score:
            result["decision"] = False
            result["reason"] = "failed_technical_analysis"
            result["threshold"] = self.min_technical_score
            result["score"] = technical_score
            return False, result
            
        # Layer 2: Performance-based adjustment
        adjustment, perf_details = self.evaluate_performance_adjustment(
            signal.symbol, signal.action
        )
        result["layers"]["performance"] = perf_details
        
        # Calculate adjusted confidence threshold
        adjusted_threshold = self.min_confidence_threshold * adjustment
        result["adjusted_threshold"] = adjusted_threshold
        
        if signal.confidence < adjusted_threshold:
            result["decision"] = False
            result["reason"] = "confidence_below_threshold"
            result["threshold"] = adjusted_threshold
            result["confidence"] = signal.confidence
            return False, result
            
        # Layer 3: Correlation guard
        should_proceed, corr_details = self.evaluate_correlation(
            signal.symbol, signal.action
        )
        result["layers"]["correlation"] = corr_details
        
        if not should_proceed:
            result["decision"] = False
            result["reason"] = "correlation_guard_triggered"
            return False, result
            
        # All checks passed
        result["decision"] = True
        result["reason"] = "all_checks_passed"
        result["confidence"] = signal.confidence
        result["threshold"] = adjusted_threshold
        result["technical_score"] = technical_score
        
        return True, result

signal_scorer = SignalScorer()
