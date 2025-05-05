import os
import json
import uuid
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from config import ASSETS  # Import ASSETS from config.py

import boto3
import redis
from oanda_api import OandaAPI
from app import app  # Import Flask app for context

logger = logging.getLogger(__name__)

# Redis connection
try:
    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        db=int(os.environ.get('REDIS_DB', 0)),
        password=os.environ.get('REDIS_PASSWORD', None),
        decode_responses=True
    )
except Exception as e:
    logger.warning(f"Could not connect to Redis: {e}")
    redis_client = None

# S3 connection
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

S3_BUCKET = os.environ.get('S3_BUCKET', 'genesis-trading-charts')

# OANDA API client
oanda_api = OandaAPI(
    api_key=os.environ.get('OANDA_API_KEY'),
    account_id=os.environ.get('OANDA_ACCOUNT_ID')
)


def get_quote(symbol: str) -> Dict[str, Any]:
    """Fetch the current quote for a symbol from OANDA"""
    try:
        # Get current price from OANDA
        response = oanda_api._make_request(f"/instruments/{symbol}/candles?count=1&price=BA&granularity=M1")
        if not response or 'candles' not in response or not response['candles']:
            logger.error(f"Failed to get quote for {symbol}")
            return {}
            
        candle = response['candles'][0]
        bid = float(candle['bid']['c'])
        ask = float(candle['ask']['c'])
        spread = ask - bid
        timestamp = candle['time']
        
        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {str(e)}")
        return {}


def take_screenshot(symbol: str) -> str:
    """Generate a technical chart for a symbol and return the path"""
    try:
        # Use chart_utils to generate a real chart with actual market data
        from chart_utils import generate_chart
        
        # Generate the chart with timeframe H1 and 100 candles
        # This will use OANDA API to get real price data
        timeframe = "H1"
        count = 100
        
        # Convert OANDA symbol format to MT5 format for directory structure
        # e.g., XAU_USD -> XAUUSD
        mt5_symbol = symbol.replace('_', '')
        
        # Generate the chart with proper indicators
        # This creates the chart and returns the path where it was saved
        chart_path = generate_chart(symbol, timeframe, count)
        
        # Extract the filename from the generated chart path
        if chart_path and os.path.exists(chart_path):
            # The chart_path looks like: static/charts/XAUUSD/XAUUSD_H1_20250505_075127.png
            # We just need the relative path for vision_worker
            vision_path = chart_path.replace('static/', '')
            logger.info(f"Generated chart for {symbol} at {chart_path}, will use path {vision_path} for vision analysis")
        else:
            # Fallback if chart_path is empty or not found
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mt5_symbol = symbol.replace('_', '')
            filename = f"{mt5_symbol}_{timeframe}_{timestamp}.png"
            
            # Ensure the charts directory exists for this symbol
            charts_dir = f"static/charts/{mt5_symbol}"
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir, exist_ok=True)
                logger.info(f"Created chart directory: {charts_dir}")
            
            vision_path = f"charts/{mt5_symbol}/{filename}"
            logger.error(f"Chart generation failed for {symbol}, using fallback path {vision_path}")

        
        # The vision_path is used as an identifier in the system
        return vision_path
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {str(e)}")
        return ""


def calculate_features(symbol: str, quote: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate additional features for the symbol"""
    try:
        # Get recent candles for ATR calculation
        response = oanda_api._make_request(f"/instruments/{symbol}/candles?count=5&price=M&granularity=M1")
        if not response or 'candles' not in response or not response['candles']:
            logger.error(f"Failed to get candles for {symbol} to calculate features")
            return {}
            
        candles = response['candles']
        
        # Calculate 1-minute ATR (Average True Range)
        atr = 0
        if len(candles) > 1:
            ranges = []
            for i in range(1, len(candles)):
                high = float(candles[i]['mid']['h'])
                low = float(candles[i]['mid']['l'])
                prev_close = float(candles[i-1]['mid']['c'])
                
                # True Range calculations
                range1 = high - low  # Current High - Current Low
                range2 = abs(high - prev_close)  # Current High - Previous Close
                range3 = abs(low - prev_close)  # Current Low - Previous Close
                
                true_range = max(range1, range2, range3)
                ranges.append(true_range)
            
            # Average True Range
            atr = sum(ranges) / len(ranges) if ranges else 0
        
        # Current spread percentage
        spread_percentage = (quote['spread'] / quote['bid']) * 100 if quote and 'bid' in quote and quote['bid'] > 0 else 0
        
        return {
            "atr_1m": atr,
            "spread_percentage": spread_percentage
        }
    except Exception as e:
        logger.error(f"Error calculating features for {symbol}: {str(e)}")
        return {}


def run(symbol: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
    """Run the capture job for a symbol"""
    if timestamp is None:
        timestamp = datetime.now()
        
    iso_timestamp = timestamp.isoformat()
    job_id = str(uuid.uuid4())
    
    try:
        # 1. Get the quote
        quote = get_quote(symbol)
        
        # 2. Take screenshot
        s3_path = take_screenshot(symbol)
        
        # 3. Calculate features
        features = calculate_features(symbol, quote)
        
        # 4. Create the payload
        payload = {
            "id": job_id,
            "ts": iso_timestamp,
            "symbol": symbol,
            "image_s3": s3_path,
            "quote": quote,
            "features": features
        }
        
        # 5. Push to Redis queue if available
        if redis_client:
            try:
                redis_client.rpush("vision_queue", json.dumps(payload))
                logger.info(f"Capture job completed for {symbol}, pushed to vision_queue")
            except Exception as e:
                logger.warning(f"Could not push to Redis queue: {e}")
        else:
            # Direct vision processing as a workaround for environments without Redis
            try:
                # Import here to avoid circular imports
                from vision_worker import DirectVisionPipeline
                # Extract just the image path for the pipeline
                mt5_symbol = symbol.replace('_', '') 
                img_path = f"static/{s3_path}"
                
                # Check if the file exists
                if os.path.exists(img_path):
                    logger.info(f"Processing chart directly: {img_path}")
                    with app.app_context():
                        pipeline = DirectVisionPipeline()
                        success = pipeline.process_chart(symbol, img_path)
                        if success:
                            logger.info(f"Successfully processed chart for {symbol} without Redis")
                        else:
                            logger.error(f"Failed to process chart for {symbol} without Redis")
                else:
                    logger.error(f"Chart file not found at {img_path}")
            except Exception as e:
                logger.error(f"Error in direct vision processing: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                
            logger.info(f"Capture job completed for {symbol}, Redis not available - attempted direct vision processing")
        
        return payload
    except Exception as e:
        logger.error(f"Error running capture job for {symbol}: {str(e)}")
        return {
            "id": job_id,
            "ts": iso_timestamp,
            "symbol": symbol,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    result = run("EUR_USD")
    print(json.dumps(result, indent=2))
