#!/usr/bin/env python3
"""
Test Signal Scoring Module

This test verifies the functionality of the signal scoring system.
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import db, Signal, Trade, SignalAction, SignalStatus, TradeStatus, TradeSide
from signal_scoring import signal_scorer

class MockSignal:
    """Mock signal for testing"""
    
    def __init__(self, id, symbol, action, confidence=0.7, context_json=None):
        self.id = id
        self.symbol = symbol
        self.action = action
        self.confidence = confidence
        self.status = SignalStatus.PENDING
        self.context_json = context_json
        
class TestSignalScoring(unittest.TestCase):
    
    def setUp(self):
        # Create some test signals
        self.signals = [
            MockSignal(1, "EUR_USD", SignalAction.BUY_NOW, 0.7, 
                       json.dumps({"rsi": 28, "macd": 0.001, "macd_signal": -0.001})),  # Strong buy signal
            MockSignal(2, "GBP_USD", SignalAction.SELL_NOW, 0.8, 
                       json.dumps({"rsi": 75, "macd": -0.002, "macd_signal": 0.001})),  # Strong sell signal
            MockSignal(3, "XAU_USD", SignalAction.ANTICIPATED_SHORT, 0.65, 
                       json.dumps({"rsi": 45, "macd": 0.001, "macd_signal": 0.003})),  # Weaker signal
            MockSignal(4, "EUR_USD", SignalAction.ANTICIPATED_LONG, 0.7, 
                       json.dumps({"rsi": 60, "macd": 0.0005, "macd_signal": 0.0008}))  # Conflicting EUR_USD signal
        ]
    
    @patch('signal_scoring.db.session.query')
    def test_technical_filter(self, mock_query):
        """Test the technical filter layer"""
        # Test signal with RSI oversold condition supporting buy
        signal1 = self.signals[0]
        tech_adj = signal_scorer.apply_technical_filter(signal1)
        self.assertGreater(tech_adj, 0, "Favorable technical conditions should provide positive adjustment")
        
        # Test signal with RSI overbought condition supporting sell
        signal2 = self.signals[1]
        tech_adj = signal_scorer.apply_technical_filter(signal2)
        self.assertGreater(tech_adj, 0, "Favorable technical conditions should provide positive adjustment")
        
    @patch('signal_scoring.db.session.query')
    def test_performance_adjustment(self, mock_query):
        """Test the performance-based adjustment layer"""
        # Setup mock trades for performance history
        mock_trades = [
            MagicMock(symbol="EUR_USD", side=TradeSide.BUY, pnl=100, status=TradeStatus.CLOSED, closed_at=datetime.now()-timedelta(days=5)),
            MagicMock(symbol="EUR_USD", side=TradeSide.BUY, pnl=150, status=TradeStatus.CLOSED, closed_at=datetime.now()-timedelta(days=3)),
            MagicMock(symbol="EUR_USD", side=TradeSide.SELL, pnl=-50, status=TradeStatus.CLOSED, closed_at=datetime.now()-timedelta(days=1)),
        ]
        mock_query.return_value.filter.return_value.all.return_value = mock_trades
        
        # Test performance adjustment for EUR_USD buy signal
        perf_adj = signal_scorer.apply_performance_adjustment("EUR_USD", SignalAction.BUY_NOW)
        self.assertGreaterEqual(perf_adj, 0, "Good historical performance should provide positive adjustment")
    
    @patch('signal_scoring.db.session.query')
    def test_correlation_check(self, mock_query):
        """Test the correlation check layer"""
        # Setup mock active signals
        mock_active_signals = [
            MagicMock(symbol="EUR_USD"),
            MagicMock(symbol="GBP_JPY")
        ]
        mock_query.return_value.filter.return_value.all.return_value = mock_active_signals
        
        # Test correlation check for EUR_USD (correlated with GBP_USD)
        has_conflict = signal_scorer.check_correlation_conflict("GBP_USD")
        self.assertTrue(has_conflict, "Should detect correlation conflict between EUR_USD and GBP_USD")
        
        # Test correlation check for XAU_USD (not correlated)
        has_conflict = signal_scorer.check_correlation_conflict("XAU_USD")
        self.assertFalse(has_conflict, "Should not detect correlation conflict for XAU_USD")
    
    @patch('signal_scoring.db.session.query')
    def test_signal_scoring(self, mock_query):
        """Test the complete signal scoring process"""
        # Setup mocks
        mock_query.return_value.filter.return_value.all.return_value = []
        
        # Test scoring for a strong buy signal
        signal1 = self.signals[0]
        final_score, should_execute = signal_scorer.score_signal(signal1)
        self.assertGreaterEqual(final_score, signal1.confidence, "Final score should be at least the base confidence")
        self.assertTrue(should_execute, "Strong buy signal should be executed")
        
        # Test scoring for a signal near threshold
        signal3 = self.signals[2]
        final_score, should_execute = signal_scorer.score_signal(signal3)
        # This could pass or fail based on the adjustments
        # Just print the result for review
        print(f"Signal 3 (XAU_USD short): Score={final_score}, Execute={should_execute}")
        
    @patch('signal_scoring.db.session.query')
    @patch('signal_scoring.db.session.commit')
    def test_filter_signals(self, mock_commit, mock_query):
        """Test the filter_signals method that processes a batch of signals"""
        # Setup mocks
        mock_query.return_value.filter.return_value.all.return_value = []
        
        # Test filtering a batch of signals
        approved_signals = signal_scorer.filter_signals(self.signals)
        
        # We expect at least some signals to be approved
        self.assertGreater(len(approved_signals), 0, "Should approve at least some signals")
        
        # Make sure commit was called to save changes
        mock_commit.assert_called_once()
        
        # Print results for review
        print(f"Approved {len(approved_signals)}/{len(self.signals)} signals")
        for signal in approved_signals:
            print(f"  - Signal {signal.id}: {signal.symbol} {signal.action}")

if __name__ == "__main__":
    unittest.main()
