#!/usr/bin/env python3
# Test script for direct vision processing without Redis
import os
import sys
import json
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import ASSETS
from capture_job import run
from app import app  # Import Flask app for context

def test_capture_signal(symbol=None):
    """Test the capture and signal generation for a symbol"""
    if symbol is None:
        # Use the first asset from the restricted list if none provided
        symbol = ASSETS[0]
        
    logger.info(f"Starting direct vision test for {symbol}")
    
    # Run the capture job directly
    result = run(symbol)
    
    # Log the result
    logger.info(f"Capture job result: {json.dumps(result, indent=2)}")
    
    # Verify if a chart was generated
    image_path = result.get('image_s3', '')
    if image_path:
        # Check if the file exists in the static directory
        local_path = f"static/{image_path}"
        if os.path.exists(local_path):
            logger.info(f"Chart generated successfully at {local_path}")
            
            # Now try direct vision processing
            try:
                from vision_worker import DirectVisionPipeline
                
                with app.app_context():
                    pipeline = DirectVisionPipeline()
                    success = pipeline.process_chart(symbol, local_path)
                    
                    if success:
                        logger.info(f"Successfully processed chart directly: {symbol}")
                    else:
                        logger.error(f"Failed to process chart directly: {symbol}")
            except Exception as e:
                logger.error(f"Error in direct vision processing: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.error(f"Chart file not found at {local_path}")
    else:
        logger.error("No image path in result")
    
    return result

def process_all_symbols():
    """Process all symbols in the restricted asset list"""
    for symbol in ASSETS:
        logger.info(f"Processing {symbol}...")
        result = test_capture_signal(symbol)
        # Wait a bit to avoid overwhelming the API
        time.sleep(2)

if __name__ == "__main__":
    # If a symbol is provided as argument, use it
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        test_capture_signal(symbol)
    else:
        # Otherwise process all symbols in the restricted list
        process_all_symbols()
