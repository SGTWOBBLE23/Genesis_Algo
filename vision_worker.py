import os
import json
import logging
import time
from typing import Dict, Any
from datetime import datetime

import redis
import requests

logger = logging.getLogger(__name__)

# Setup a direct approach without Redis
from app import db, Signal, SignalAction, SignalStatus, app

# Redis will be mocked since it's not available
redis_client = None

class DirectVisionPipeline:
    """A direct approach to vision processing without Redis"""
    
    @staticmethod
    def process_chart(symbol, image_path):
        """Process a chart image directly"""
        try:
            logger.info(f"Processing chart for {symbol} at {image_path}")
            # Check if the image file exists
            if not os.path.exists(image_path):
                logger.error(f"Image file does not exist: {image_path}")
                return False
                
            vision_result = analyze_image(image_path)
            
            if not vision_result or 'action' not in vision_result:
                logger.error(f"Failed to analyze chart for {symbol}")
                return False
                
            # Create a signal directly in the database
            signal = Signal(
                symbol=symbol,
                action=vision_result['action'],
                entry=vision_result.get('entry'),
                sl=vision_result.get('sl'),
                tp=vision_result.get('tp'),
                confidence=vision_result.get('confidence', 0.5),
                status=SignalStatus.PENDING,
                context_json=json.dumps({
                    'source': 'direct_vision_pipeline',
                    'image_path': image_path,
                    'processed_at': datetime.now().isoformat()
                })
            )
            
            db.session.add(signal)
            db.session.commit()
            
            logger.info(f"Created signal for {symbol} with action {vision_result['action']}")
            return True
            
        except Exception as e:
            logger.error(f"Error in direct vision pipeline: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

# OpenAI API configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
VISION_MODEL = os.environ.get('VISION_MODEL', 'gpt-4o')
VISION_API_URL = 'https://api.openai.com/v1/chat/completions'

MAX_RETRIES = 2


def analyze_image(image_path: str) -> Dict[str, Any]:
    """Send image to Vision API for analysis with OpenAI"""
    try:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found in environment variables")
            return {}
            
        logger.info(f"Sending request to OpenAI Vision API")
        
        # Read the local image file
        import base64
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return {}
        
        # Read the image file and encode it
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Extract symbol from the path for better context
        try:
            # Format is typically static/charts/SYMBOL/filename.png
            parts = image_path.split('/')
            symbol_index = parts.index('charts') + 1
            symbol = parts[symbol_index] if symbol_index < len(parts) else 'UNKNOWN'
        except:
            symbol = "UNKNOWN"
        
        # Build request for OpenAI API
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Construct a detailed prompt for the vision model
        system_prompt = """
        You are GENESIS, an expert forex trading analyst and professional chart pattern recognition system. Your task is to analyze forex charts and provide precise trading signals with high accuracy.
        
        CHART ANALYSIS GUIDELINES:
        1. Focus on the following technical indicators visible in the chart:
           - EMA 20 (Blue line) and EMA 50 (Orange line) - Identify trend direction and potential crossovers
           - RSI (Relative Strength Index) - Identify overbought/oversold conditions and divergence
           - MACD (Moving Average Convergence Divergence) - Identify momentum shifts and crossovers
           - ATR (Average True Range) - Assess volatility for proper stop loss placement
           - Japanese candlestick patterns - Identify key reversal patterns like engulfing, doji, hammer, etc.
        
        2. Prioritize these high-reliability trading patterns:
           - Strong trend continuation after pullbacks to EMA 20/50
           - Clear breakouts from support/resistance with increased volume
           - Double tops/bottoms with confirmation
           - Head and shoulders patterns with neckline breaks
           - Clear divergence between price and RSI/MACD
           - Strong rejection candles at key levels (pin bars)
        
        3. Risk management calculations:
           - Stop loss placement: Use nearest swing high/low based on chart timeframe
           - For aggressive signals: 1:2 risk-reward at minimum (prefer 1:3)
           - For conservative signals: 1:1.5 risk-reward at minimum (prefer 1:2)
           - Never place stop loss inside the ATR range of recent price action
        
        SIGNAL CLASSIFICATION:
        - BUY_NOW: Immediate long entry, high confidence signal, with clear support and upward momentum
        - SELL_NOW: Immediate short entry, high confidence signal, with clear resistance and downward momentum
        - ANTICIPATED_LONG: Potential future buy setup forming, waiting for specific trigger or confirmation
        - ANTICIPATED_SHORT: Potential future sell setup forming, waiting for specific trigger or confirmation
        
        CONFIDENCE SCORE GUIDELINES:
        - 0.9-1.0: Perfect setup with multiple confirming factors (trend, indicators, pattern, volume)
        - 0.8-0.89: Strong setup with 3+ confirming factors
        - 0.7-0.79: Good setup with 2+ confirming factors
        - 0.6-0.69: Reasonable setup with limited confirmation
        - Below 0.6: Weak setup, avoid trading
        
        RESPONSE FORMAT:
        You must respond with a valid JSON object containing only these fields:
        {"action": "BUY_NOW|SELL_NOW|ANTICIPATED_LONG|ANTICIPATED_SHORT", "entry": float, "sl": float, "tp": float, "confidence": float}
        
        If no valid trading opportunity exists, respond with confidence below 0.6 for the most probable setup.
        """
        
        # Construct payload with the image
        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this {symbol} forex chart and identify the most promising trading opportunity if one exists. Assess the current trend, support/resistance levels, and indicator readings (EMA 20/50, RSI, MACD, ATR). Identify any high-probability chart patterns or setups. Provide precise entry, stop loss and take profit levels based on the visible price action. If using fractional pips, round to standard 5-digit price format."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        # Send to OpenAI Vision API
        logger.info("Sending request to OpenAI Vision API")
        response = requests.post(VISION_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            
            # Extract JSON from the response
            import json
            try:
                trading_signal = json.loads(content)
                # Validate required fields
                required_fields = ['action', 'entry', 'sl', 'tp', 'confidence']
                if all(field in trading_signal for field in required_fields):
                    logger.info(f"Successfully analyzed chart: {trading_signal}")
                    return trading_signal
                else:
                    logger.error(f"Missing required fields in response: {content}")
            except json.JSONDecodeError:
                logger.error(f"Could not parse JSON from response: {content}")
        
        logger.error(f"Unexpected response format from OpenAI: {result}")
        return {}

    except Exception as e:
        logger.error(f"Error analyzing image {image_path}: {str(e)}")
        return {}


def process_vision_queue():
    """Process items from the Redis 'vision_queue' and push to 'signal_queue'."""
    if not redis_client:
        logger.error("Redis client not available, cannot process vision queue")
        return

    while True:
        try:
            # Pop item from vision_queue
            # This would normally attempt to get an item from the queue
            # Since we're not using Redis, we'll skip this logic
            item = None
            if not item:
                time.sleep(1)
                continue

            _, payload_str = item
            payload = json.loads(payload_str)

            job_id = payload.get('id')
            symbol = payload.get('symbol')
            image_s3 = payload.get('image_s3')

            if not job_id or not symbol or not image_s3:
                logger.error(f"Invalid payload format: {payload_str}")
                continue

            logger.info(f"Processing vision job {job_id} for {symbol}")

            # Send image to Vision API (with retries)
            retry_count = 0
            vision_result: Dict[str, Any] = {}
            while retry_count <= MAX_RETRIES:
                vision_result = analyze_image(image_s3)
                if vision_result and 'action' in vision_result:
                    break  # success
                retry_count += 1
                if retry_count <= MAX_RETRIES:
                    logger.warning(
                        f"Retrying vision analysis for {job_id}, attempt {retry_count}")
                    time.sleep(2 ** retry_count)

            if not vision_result or 'action' not in vision_result:
                logger.error(
                    f"Failed to analyze image for job {job_id} after {MAX_RETRIES} retries")
                try:
                    alert_payload = {
                        'type': 'error',
                        'source': 'vision_worker',
                        'message': f"Failed to analyze image for {symbol} (job {job_id})",
                        'job_id': job_id,
                        'symbol': symbol
                    }
                    redis_client.publish('alerts', json.dumps(alert_payload))
                except Exception as e:
                    logger.error(f"Could not publish alert: {e}")
                continue

            # ----------------------------------------------------------------
            # HOT‑FIX: Ensure entry price for BUY_NOW / SELL_NOW signals is
            #          synced with the most recent quote captured earlier.
            # ----------------------------------------------------------------
            try:
                action = vision_result.get('action')
                if action in {'BUY_NOW', 'SELL_NOW'}:
                    live_bid = payload.get('quote', {}).get('bid')

                    if live_bid is not None:
                        old_entry = float(vision_result.get('entry', 0))
                        new_entry = round(float(live_bid), 5)

                        percent_cutoff = 0.0002            # 0.02 % (adjust if you like)
                        max_deviation  = live_bid * percent_cutoff
                        diff = abs(old_entry - new_entry)

                        if diff > max_deviation:
                            logger.info(
                                f"Overriding Vision entry {old_entry} → {new_entry} "
                                f"(Δ={diff:.5f} > {max_deviation:.5f}, {percent_cutoff*100:.3f}% cutoff)")
                            vision_result['entry'] = new_entry
            except Exception as e:
                logger.error(f"Error applying entry override: {e}")
            # ----------------------------------------------------------------

            # Merge Vision result with original payload
            enriched_payload = payload.copy()
            enriched_payload['vision_result'] = vision_result

            # Push to signal queue
            try:
                redis_client.rpush('signal_queue', json.dumps(enriched_payload))
                logger.info(
                    f"Processed vision job {job_id} for {symbol}, pushed to signal_queue")
            except Exception as e:
                logger.error(f"Could not push to signal_queue: {e}")

        except Exception as e:
            logger.error(f"Error processing vision queue: {str(e)}")
            time.sleep(1)


def process_charts_directory():
    """Process all charts in static/charts directory"""
    import os
    import glob
    import time
    from datetime import datetime
    
    try:
        logger.info("Starting direct charts processing...")
        
        # Process only our restricted symbols
        symbols = ['XAU_USD', 'GBP_JPY', 'GBP_USD', 'EUR_USD', 'USD_JPY']
        
        # Create app context for database operations
        with app.app_context():
            # Ensure static/charts directory exists
            charts_dir = "static/charts"
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)
                logger.info(f"Created charts directory: {charts_dir}")
                
            # Create directories for each symbol if they don't exist
            for symbol in symbols:
                mt5_symbol = symbol.replace('_', '')
                chart_dir = f"{charts_dir}/{mt5_symbol}"
                if not os.path.exists(chart_dir):
                    os.makedirs(chart_dir)
                    logger.info(f"Created chart directory for {symbol}: {chart_dir}")
                    # Generate a test chart for this symbol
                    from chart_utils import generate_chart
                    chart_path = generate_chart(symbol)
                    if chart_path:
                        logger.info(f"Generated test chart for {symbol}: {chart_path}")
                    else:
                        logger.error(f"Failed to generate test chart for {symbol}")
                    # Wait a bit to not overwhelm the API
                    time.sleep(1)
            
            # Process the charts
            pipeline = DirectVisionPipeline()
            for symbol in symbols:
                # Look for the most recent chart for this symbol
                mt5_symbol = symbol.replace('_', '')
                chart_dir = f"{charts_dir}/{mt5_symbol}"
                
                # Get all PNG files in the directory, sorted by modification time (newest first)
                chart_files = glob.glob(f"{chart_dir}/*.png")
                if not chart_files:
                    logger.warning(f"No chart files found in {chart_dir}")
                    continue
                    
                chart_files.sort(key=os.path.getmtime, reverse=True)
                latest_chart = chart_files[0]
                
                logger.info(f"Processing latest chart for {symbol}: {latest_chart}")
                success = pipeline.process_chart(symbol, latest_chart)
                
                if success:
                    logger.info(f"Successfully processed chart for {symbol}")
                else:
                    logger.error(f"Failed to process chart for {symbol}")
                    
                # Wait a bit to not overwhelm the OpenAI API
                time.sleep(1)
                    
    except Exception as e:
        logger.error(f"Error in process_charts_directory: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Setup more verbose logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("Starting Vision Worker with more verbose logging...")
    
    # Check OpenAI API key
    if not OPENAI_API_KEY:
        logger.error("No OpenAI API key found! Vision analysis will fail.")
    else:
        logger.info("OpenAI API key found.")
    
    # Since Redis is not available, use direct processing
    logger.info("Redis not available, using direct chart processing instead")
    
    # Import datetime here for use in the log
    from datetime import datetime
    
    # Process all charts in the directory
    process_charts_directory()
