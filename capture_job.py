import os
import json
import uuid
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

import boto3
import redis
from oanda_api import OandaAPI

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
    """Take a screenshot of the chart and upload to S3"""
    try:
        # We'll simulate this function as the actual implementation
        # would require browser automation or MT5 API integration
        # In a real implementation, this would:
        # 1. Capture the chart image for the symbol
        # 2. Save it temporarily
        # 3. Upload to S3
        # 4. Return the S3 path
        
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{timestamp}.png"
        s3_path = f"charts/{symbol}/{filename}"
        
        # In a real implementation, we would save and upload the actual screenshot
        # For simulation, we'll just log and return the path
        logger.info(f"Simulated taking screenshot for {symbol} and uploading to S3 at {s3_path}")
        
        return s3_path
    except Exception as e:
        logger.error(f"Error taking screenshot for {symbol}: {str(e)}")
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
            logger.info(f"Capture job completed for {symbol}, Redis not available - data not queued")
        
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
