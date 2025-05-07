import os
import json
import uuid
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Configure logging first
logger = logging.getLogger(__name__)

# Import configuration from config.py
from config import ASSETS, CHARTS_DIR, DEFAULT_TIMEFRAME, mt5_to_oanda, oanda_to_mt5

# Use try/except for dependencies that might not be available
try:
    import boto3
    S3_AVAILABLE = True
except ImportError:
    boto3 = None
    S3_AVAILABLE = False
    logger.info("boto3 not available, S3 functionality disabled")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
    logger.info("redis not available, queue functionality disabled")

from oanda_api import OandaAPI
from app import app  # Import Flask app for context

# Redis connection - only try if Redis is available
redis_client = None
if REDIS_AVAILABLE:
    try:
        # Create Redis client
        redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=int(os.environ.get('REDIS_DB', 0)),
            password=os.environ.get('REDIS_PASSWORD', None),
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        redis_client = None
else:
    logger.info("Redis client not created as Redis is not available")

# S3 connection - only try if boto3 is available
s3_client = None
S3_BUCKET = os.environ.get('S3_BUCKET', 'genesis-trading-charts')
if S3_AVAILABLE:
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        logger.info("Successfully created S3 client")
    except Exception as e:
        logger.warning(f"Could not connect to S3: {e}")
        s3_client = None
else:
    logger.info("S3 client not created as boto3 is not available")

# OANDA API client
oanda_api = OandaAPI(
    api_key=os.environ.get('OANDA_API_KEY'),
    account_id=os.environ.get('OANDA_ACCOUNT_ID')
)

# Initialize DirectVisionPipeline if available
try:
    from vision_worker import DirectVisionPipeline
    # Don't instantiate here to avoid circular imports
    # We'll create instances when needed in the run() function
    DIRECT_VISION_AVAILABLE = True
    logger.info("DirectVisionPipeline is available for use")
except ImportError:
    DIRECT_VISION_AVAILABLE = False
    logger.warning("DirectVisionPipeline not available, vision functionality limited")



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


def take_screenshot(
    symbol: str,
    timeframe: str = "H1",
    count: int = 100,
) -> str:
    """
    Generate a technical chart for `symbol` at the requested `timeframe`
    and return the path *relative to* the `static/` folder (so Vision can
    load it).

    Args:
        symbol: Trading instrument, e.g. "XAU_USD".
        timeframe: "M15", "H1", "D1", … (default "H1").
        count: How many candles to include (default 100).

    Returns:
        vision_path: Path string like "charts/XAUUSD/XAUUSD_H1_20250507_093002.png".
                     Empty string if chart generation fails.
    """
    try:
        # Generate the chart with actual market data
        from chart_utils import generate_chart

        # Convert OANDA-style "XAU_USD" → "XAUUSD" for dir structure
        mt5_symbol = symbol.replace("_", "")

        # Try the real chart generator first
        chart_path = generate_chart(symbol, timeframe, count)

        if chart_path and os.path.exists(chart_path):
            # chart_path looks like: static/charts/XAUUSD/XAUUSD_H1_20250507_093002.png
            vision_path = chart_path.replace("static/", "")
            logger.info(
                f"Generated {timeframe} chart for {symbol} at {chart_path} "
                f"(Vision path: {vision_path})"
            )
        else:
            # Fallback stub: create an empty file path so pipeline doesn’t crash
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            charts_dir = f"static/charts/{mt5_symbol}"
            os.makedirs(charts_dir, exist_ok=True)

            filename = f"{mt5_symbol}_{timeframe}_{timestamp}.png"
            vision_path = f"charts/{mt5_symbol}/{filename}"
            logger.error(
                f"Chart generation failed for {symbol}, "
                f"using fallback path {vision_path}"
            )

        return vision_path

    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {e}")
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


def run(
    symbol: str,
    timestamp: Optional[datetime] = None,
    timeframe: str = "H1",                 # ← new keyword, default keeps old behaviour
) -> Dict[str, Any]:
    """
    Run the capture job for a symbol.

    Args:
        symbol: Trading instrument (e.g., "XAUUSD").
        timestamp: Optional explicit timestamp; defaults to now().
        timeframe: Chart granularity to capture ("M15", "H1", ...).
    """
    if timestamp is None:
        timestamp = datetime.now()

    iso_timestamp = timestamp.isoformat()
    job_id = str(uuid.uuid4())

    try:
        # 1. Get the quote
        quote = get_quote(symbol)

        # 2. Take screenshot at requested timeframe
        s3_path = take_screenshot(symbol, timeframe)

        # 3. Calculate features
        features = calculate_features(symbol, quote)

        # 4. Create the payload
        payload = {
            "id": job_id,
            "ts": iso_timestamp,
            "symbol": symbol,
            "timeframe": timeframe,        # optional—but handy for logging/debug
            "image_s3": s3_path,
            "quote": quote,
            "features": features,
        }

        # 5. Push to Redis queue if available
        if redis_client:
            try:
                redis_client.rpush("vision_queue", json.dumps(payload))
                logger.info(
                    f"Capture job completed for {symbol} ({timeframe}), pushed to vision_queue"
                )
            except Exception as e:
                logger.warning(f"Could not push to Redis queue: {e}")
        else:
            # Direct vision processing as a workaround for environments without Redis
            try:
                # Import here to avoid circular imports
                from vision_worker import DirectVisionPipeline

                # Extract just the image path for the pipeline
                mt5_symbol = symbol.replace("_", "")
                img_path = f"static/{s3_path}"

                # Check if the file exists
                if os.path.exists(img_path):
                    logger.info(f"Processing chart directly: {img_path}")
                    with app.app_context():
                        pipeline = DirectVisionPipeline()
                        success = pipeline.process_chart(symbol, img_path)
                        if success:
                            logger.info(
                                f"Successfully processed chart for {symbol} ({timeframe}) without Redis"
                            )
                        else:
                            logger.error(
                                f"Failed to process chart for {symbol} ({timeframe}) without Redis"
                            )
                else:
                    logger.error(f"Chart file not found at {img_path}")
            except Exception as e:
                logger.error(f"Error in direct vision processing: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())

            logger.info(
                f"Capture job completed for {symbol} ({timeframe}), Redis not available - attempted direct vision processing"
            )

        return payload
    except Exception as e:
        logger.error(f"Error running capture job for {symbol}: {str(e)}")
        return {
            "id": job_id,
            "ts": iso_timestamp,
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(e),
        }


if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    result = run("EUR_USD")
    print(json.dumps(result, indent=2))
