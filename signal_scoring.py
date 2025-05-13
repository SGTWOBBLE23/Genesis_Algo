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
                logger.info(f"Reloaded weights (v{data.get('version')})")
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
        
    def _normalize_symbol_for_db(self, symbol: str) -> str:
        """Convert symbol with underscores (XAU_USD) to format stored in database (XAUUSD)"""
        return symbol.replace('_', '') if symbol else symbol
            
    def __init__(self):
        """Initialize the SignalScorer with default settings"""
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
            },
            #'BTCUSD': {             # Add entire new entry
             #   'EURUSD': 0.25,     # Low correlation
              #  'GBPUSD': 0.20,     # Low correlation
               # 'USDJPY': -0.15,    # Very low negative correlation
                #'GBPJPY': 0.10,     # Almost no correlation
                #'XAUUSD': 0.40      # Moderate correlation with gold
            #}
        }

        # Trade side mapping
        self.action_to_side = {
            SignalAction.BUY_NOW: TradeSide.BUY,
            SignalAction.SELL_NOW: TradeSide.SELL,
            SignalAction.ANTICIPATED_LONG: TradeSide.BUY,
            SignalAction.ANTICIPATED_SHORT: TradeSide.SELL
        }

    def merge_or_update(self, signal: "Signal") -> bool:

        return True
        """
        If an open signal of the **same symbol + action** exists and the
        entry prices are within a small tolerance, roll this new evidence
        into the existing one instead of keeping a duplicate.

        Returns True  ↠  We *kept* the new signal (no merge)
                False ↠  We *merged* and deleted the newcomer
        """
        def _pip_tol(sym: str) -> float:
            if sym.startswith(("XAU", "XAG")):           # metals
                return 1.0                               # $1 ≈ 10 ‘pipettes’
            if sym.endswith("JPY"):                      # 3-dp JPY pairs
                return 0.10                              # 0.10 ≈ 10 pips
            return 0.001                                 # 0.0010 ≈ 10 pips (4-dp FX)

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

        # ── Merge logic ───────────────────────────────────────────────
        #
        # Combined confidence  = 1 − ∏(1 − cᵢ)
        # (probabilistic union of independent confirmations)
        #
        combined = 1 - (1 - sibling.confidence) * (1 - signal.confidence)
        sibling.confidence = round(combined, 4)

        # Append provenance for audit
        ctx = sibling.context
        merged = ctx.get("merged_ids", [])
        merged.append(signal.id)
        ctx["merged_ids"] = merged
        sibling.context = ctx

        # Soft-delete the newcomer (CANCELLED → keeps the row for traceability)
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
            # ── 1. Symbol format for OANDA ──────────────────────────────────
            oanda_symbol = symbol
            if '_' not in symbol:
                oanda_symbol = re.sub(r'([A-Z]{3})([A-Z]{3})', r'\1_\2', symbol)

            # ── 2. Fetch last 100 H1 candles ────────────────────────────────
            candles = fetch_candles(oanda_symbol, timeframe="H1", count=100)
            if not candles:
                logger.warning(f"No candle data for {symbol}")
                return 0.5, {"error": "no_candles"}

            df = pd.DataFrame(
                {
                    "time":      c.get("time", c["timestamp"]),   # ← safe access
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

            # ── 3. Indicators ───────────────────────────────────────────────
            df["rsi"]       = self._calculate_rsi(df["close"])
            df["macd"], df["signal"], df["histogram"] = self._calculate_macd(df["close"])
            df["ema20"]     = self._calculate_ema(df["close"], 20)
            df["ema50"]     = self._calculate_ema(df["close"], 50)
            df["ema200"]    = self._calculate_ema(df["close"], 200)

            latest = df.iloc[-1]
            prev   = df.iloc[-2] if len(df) > 1 else latest

            # ── 4. Build factor-level scores (unchanged logic) ─────────────
            scores: dict[str, float] = {}
            details: dict[str, float | str | dict] = {
                "current_price": float(latest["close"]),
                "rsi":           float(latest["rsi"]),
                "macd":          float(latest["macd"]),
                "signal":        float(latest["signal"]),
                "ema20":         float(latest["ema20"]),
                "ema50":         float(latest["ema50"]),
                "ema200":        float(latest["ema200"]),
            }

            # 4-A. RSI
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

            # 4-B. MACD
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

            # 4-C. Trend (EMA stack)
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

            # 4-D. Entry-price sanity check
            if entry_price is not None:
                diff = abs(entry_price - latest["close"]) / latest["close"]
                if diff < 0.001:
                    scores["entry_price"] = 1.0; details["entry_price_evaluation"] = "excellent"
                elif diff < 0.005:
                    scores["entry_price"] = 0.8; details["entry_price_evaluation"] = "good"
                elif diff < 0.01:
                    scores["entry_price"] = 0.6; details["entry_price_evaluation"] = "acceptable"
                else:
                    scores["entry_price"] = 0.2; details["entry_price_evaluation"] = "poor"

            # ── 5. Weighted aggregation using the JSON table ────────────────
            if not scores:
                logger.warning(f"No tech scores for {symbol}")
                return 0.5, {"error": "no_scores"}

            # Pull live weights (falls back to 1.0 if key absent)
            weights_live = {
                k: weight_cache.weight(k if k != "entry_price" else "price_distance_to_ema20")
                for k in scores
            }

            # Normalise so they sum to 1
            total_w = sum(weights_live.values())
            weights_norm = {k: v / total_w for k, v in weights_live.items()}

            technical_score = round(
                sum(scores[k] * weights_norm[k] for k in scores), 4
            )

            from ml.model_inference import predict_one
            latest_row = df.iloc[-1]                # last candle's feature row
            ml_prob = predict_one(symbol, "H1", latest_row)

            # ------------------------------------------------------------------
            # ML‑only composite: 70 % indicator score  +  30 % scaled ML probability
            # ------------------------------------------------------------------
            ml_prob_scaled = max(0.5, min(1.0, ml_prob * 4))  # 0.02→0.5, 0.25→1.0
            technical_score = round(0.7 * technical_score + 0.3 * ml_prob_scaled, 4)

            # Debug details
            details["ml_prob"] = ml_prob
            details["ml_prob_scaled"] = ml_prob_scaled

            details["component_scores"] = scores
            details["weights_used"]     = weights_norm
            details["final_technical_score"] = technical_score

            return technical_score, details

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Technical eval error: %s", exc, exc_info=True)
            return 0.5, {"error": str(exc)}

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
            
            # Convert XAU_USD format to XAUUSD for database queries
            db_symbol = self._normalize_symbol_for_db(symbol)
            
            logger.info(f"Looking for {symbol} (DB: {db_symbol}) {side.name} trades closed after {cutoff_date}")

            # First check if we have any trades at all for this symbol
            total_trades_count = Trade.query.filter(
                Trade.symbol == db_symbol,
                Trade.side == side,
                Trade.status == TradeStatus.CLOSED
            ).count()

            logger.info(f"Found {total_trades_count} total {symbol} {side.name} trades in database")

            # Now get the trades within our evaluation period
            trades = Trade.query.filter(
                Trade.symbol == db_symbol,
                Trade.side == side,
                Trade.status == TradeStatus.CLOSED,
                Trade.closed_at >= cutoff_date
            ).all()

            trade_count = len(trades)
            logger.info(f"Found {trade_count} {symbol} {side.name} trades within the {self.evaluation_period_days}-day evaluation period")

            if not trades:
                logger.info(f"No recent trade history for {symbol} {side.name}, using default adjustment")
                return 1.0, {"reason": "No recent trade history", "total_trades_in_db": total_trades_count}

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
            # Convert incoming symbol to database format (remove underscore)
            db_symbol = self._normalize_symbol_for_db(symbol)
            
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
                if trade_symbol == db_symbol:
                    continue

                # Convert both to non-underscore format for correlation lookup
                corr_symbol = self._normalize_symbol_for_db(symbol) 
                corr_trade_symbol = trade_symbol  # Already in DB format without underscore

                # Get base correlation
                if corr_trade_symbol in self.pair_correlations and corr_symbol in self.pair_correlations[corr_trade_symbol]:
                    base_correlation = self.pair_correlations[corr_trade_symbol][corr_symbol]
                elif corr_symbol in self.pair_correlations and corr_trade_symbol in self.pair_correlations[corr_symbol]:
                    base_correlation = self.pair_correlations[corr_symbol][corr_trade_symbol]
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

            if not self.merge_or_update(signal):
                return False, {"decision": "merged_into_existing"}
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

            # Log detailed information about the adjustment
            logger.info(f"Performance adjustment for {signal.symbol} {signal.action.name}: " +
                       f"Base threshold {self.min_confidence_threshold:.2f} * Factor {adjustment_factor:.2f} = " +
                       f"Adjusted threshold {adjusted_threshold:.2f}")

            # Log whether the signal passes the adjusted threshold
            if signal.confidence >= adjusted_threshold:
                logger.info(f"Signal confidence {signal.confidence:.2f} meets adjusted threshold {adjusted_threshold:.2f}")
            else:
                logger.info(f"Signal confidence {signal.confidence:.2f} below adjusted threshold {adjusted_threshold:.2f}")

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
