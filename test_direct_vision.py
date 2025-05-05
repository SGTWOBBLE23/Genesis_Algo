#!/usr/bin/env python3

"""
Test script for the DirectVisionPipeline class in vision_worker.py

This script tests the direct image analysis pipeline that processes chart images
without requiring Redis. It's a workaround for environments without Docker/Redis.

Usage:
    python test_direct_vision.py
"""

import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import DirectVisionPipeline
try:
    from vision_worker import DirectVisionPipeline, analyze_image
    from config import ASSETS
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Create a Flask application context for database operations
try:
    from app import app
    # This is needed as we're using Flask-SQLAlchemy, which requires an app context
    ctx = app.app_context()
    ctx.push()
    logger.info("Successfully created Flask application context")
except ImportError as e:
    logger.error(f"Failed to import Flask app: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error creating Flask application context: {e}")
    sys.exit(1)

def test_analyze_image():
    """Test the analyze_image function with a sample chart"""
    # Check if OpenAI API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        return False
    
    # Generate or use an existing chart
    try:
        from chart_utils import generate_chart
        
        # Use EURUSD as a test symbol
        test_symbol = "EUR_USD"
        
        # Generate a chart or use an existing one
        logger.info(f"Generating test chart for {test_symbol}")
        chart_path = generate_chart(test_symbol)
        
        if not chart_path or not os.path.exists(chart_path):
            logger.error(f"Failed to generate chart for {test_symbol}")
            return False
        
        logger.info(f"Generated chart at {chart_path}")
        
        # Test the analyze_image function
        logger.info(f"Testing analyze_image with {chart_path}")
        result = analyze_image(chart_path)
        
        if not result or not isinstance(result, dict):
            logger.error(f"analyze_image returned invalid result: {result}")
            return False
        
        logger.info(f"analyze_image returned: {json.dumps(result, indent=2)}")
        return True
        
    except Exception as e:
        logger.error(f"Error in test_analyze_image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_direct_vision_pipeline():
    """Test the DirectVisionPipeline with a sample chart"""
    try:
        # Create the pipeline
        pipeline = DirectVisionPipeline()
        
        # Generate or use existing charts
        from chart_utils import generate_chart
        
        success_count = 0
        total_count = 0
        
        # Test with a sample of ASSETS
        test_symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
        for symbol in test_symbols:
            total_count += 1
            # Generate a chart or use an existing one
            logger.info(f"Generating test chart for {symbol}")
            chart_path = generate_chart(symbol)
            
            if not chart_path or not os.path.exists(chart_path):
                logger.error(f"Failed to generate chart for {symbol}")
                continue
            
            logger.info(f"Generated chart at {chart_path}")
            
            # Test the pipeline
            logger.info(f"Testing DirectVisionPipeline with {chart_path}")
            success = pipeline.process_chart(symbol, chart_path)
            
            if success:
                logger.info(f"Successfully processed {symbol} chart")
                success_count += 1
            else:
                logger.error(f"Failed to process {symbol} chart")
        
        logger.info(f"Processed {success_count}/{total_count} charts successfully")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error in test_direct_vision_pipeline: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to run tests"""
    logger.info("Starting direct vision pipeline tests...")
    
    # Test individual image analysis
    logger.info("\n=== Testing analyze_image ===\n")
    image_analysis_success = test_analyze_image()
    
    # Test the complete pipeline if image analysis succeeded
    if image_analysis_success:
        logger.info("\n=== Testing DirectVisionPipeline ===\n")
        pipeline_success = test_direct_vision_pipeline()
    else:
        logger.error("Skipping DirectVisionPipeline test as image analysis failed")
        pipeline_success = False
    
    # Report overall results
    if image_analysis_success and pipeline_success:
        logger.info("\n✅ All tests passed successfully!")
        return 0
    else:
        logger.error("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        # Clean up Flask context
        try:
            ctx.pop()
        except Exception:
            pass
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Clean up Flask context
        try:
            ctx.pop()
        except Exception:
            pass
        sys.exit(1)
