#!/usr/bin/env python3

"""
Unit tests for signal scoring module
"""

import unittest
import logging
from datetime import datetime
from app import app, db, Signal, SignalAction, SignalStatus
from signal_scoring import signal_scorer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSignalScoring(unittest.TestCase):
    """Test cases for signal scoring functionality"""
    
    def setUp(self):
        # Set up test environment
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Create test signal
        self.test_signal = Signal(
            symbol="EURUSD",
            action=SignalAction.BUY_NOW,
            entry=1.13500,
            sl=1.13000,
            tp=1.14000,
            confidence=0.75,
            status=SignalStatus.PENDING,
            created_at=datetime.now()
        )
    
    def tearDown(self):
        # Clean up
        self.app_context.pop()
    
    def test_technical_evaluation(self):
        """Test technical evaluation component"""
        technical_score, details = signal_scorer.evaluate_technical_conditions(
            symbol="EURUSD",
            action=SignalAction.BUY_NOW
        )
        
        logger.info(f"Technical evaluation result: {technical_score}")
        logger.info(f"Technical evaluation details: {details}")
        
        # Verify the score is within expected range
        self.assertTrue(0 <= technical_score <= 1, "Technical score should be between 0 and 1")
        
        # Verify details contain expected keys
        expected_keys = ["current_price", "rsi", "macd", "signal", "ema20", "ema50"]
        for key in expected_keys:
            self.assertIn(key, details, f"Technical details should contain {key}")
    
    def test_performance_adjustment(self):
        """Test performance-based adjustment"""
        adjustment_factor, details = signal_scorer.evaluate_performance_adjustment(
            symbol="EURUSD",
            action=SignalAction.BUY_NOW
        )
        
        logger.info(f"Performance adjustment factor: {adjustment_factor}")
        logger.info(f"Performance adjustment details: {details}")
        
        # Verify adjustment factor is within expected range
        self.assertTrue(0.7 <= adjustment_factor <= 1.3, 
                        "Adjustment factor should be between 0.7 and 1.3")
    
    def test_correlation_analysis(self):
        """Test correlation analysis"""
        should_proceed, details = signal_scorer.evaluate_correlation(
            symbol="EURUSD",
            action=SignalAction.BUY_NOW
        )
        
        logger.info(f"Correlation analysis result: {should_proceed}")
        logger.info(f"Correlation analysis details: {details}")
        
        # Verify correlation check result is boolean
        self.assertIsInstance(should_proceed, bool, "Correlation result should be boolean")
    
    def test_full_signal_evaluation(self):
        """Test complete signal evaluation process"""
        should_execute, details = signal_scorer.should_execute_signal(self.test_signal)
        
        logger.info(f"Signal evaluation result: {should_execute}")
        logger.info(f"Signal evaluation details: {details}")
        
        # Verify result is boolean
        self.assertIsInstance(should_execute, bool, "Evaluation result should be boolean")
        
        # Verify details contain decision
        self.assertIn("decision", details, "Evaluation details should contain decision")

if __name__ == "__main__":
    unittest.main()
