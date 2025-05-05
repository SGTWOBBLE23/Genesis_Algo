#!/usr/bin/env python3
"""
Simple test script to verify the DirectVisionPipeline and chart generation are working.

Usage:
    python test_direct_pipeline.py
"""

import os
import logging
from datetime import datetime
from app import app
from config import ASSETS, DEFAULT_TIMEFRAME

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chart_generation():
    """Test chart generation for a single asset"""
    from chart_utils import generate_chart
    
    # Just test with EUR_USD to make it faster
    symbol = "EUR_USD"
    logger.info(f"Generating chart for {symbol}")
    chart_path = generate_chart(symbol, DEFAULT_TIMEFRAME, count=100)
    
    if chart_path and os.path.exists(chart_path):
        logger.info(f"✅ Successfully generated chart for {symbol} at {chart_path}")
        return chart_path
    else:
        logger.error(f"❌ Failed to generate chart for {symbol}")
        return None

def test_direct_vision():
    """Test the DirectVisionPipeline for a single asset"""
    from vision_worker import DirectVisionPipeline
    
    # Create the pipeline
    pipeline = DirectVisionPipeline()
    
    # First generate or use existing charts
    from chart_utils import generate_chart
    
    with app.app_context():
        # Just test with EUR_USD to make it faster
        symbol = "EUR_USD"
        logger.info(f"Testing DirectVisionPipeline with {symbol}")
        
        # Generate a chart
        chart_path = generate_chart(symbol, DEFAULT_TIMEFRAME, count=100)
        
        if not chart_path or not os.path.exists(chart_path):
            logger.error(f"❌ Failed to generate chart for {symbol}, skipping vision test")
            return
        
        logger.info(f"Using chart path: {chart_path}")
        
        # Process the chart with the pipeline
        success = pipeline.process_chart(symbol, chart_path)
        
        if success:
            logger.info(f"✅ Successfully processed {symbol} chart with DirectVisionPipeline")
        else:
            logger.error(f"❌ Failed to process {symbol} chart with DirectVisionPipeline")

def main():
    """Main function"""
    logger.info("Starting tests...")
    
    # Test chart generation
    logger.info("\n=== Testing Chart Generation ===\n")
    test_chart_generation()
    
    # Test direct vision pipeline
    logger.info("\n=== Testing DirectVisionPipeline ===\n")
    test_direct_vision()
    
    logger.info("\nTests completed!")

if __name__ == "__main__":
    main()
