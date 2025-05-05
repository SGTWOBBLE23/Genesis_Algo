import os
import json
import logging
import time
from typing import Dict, Any

import redis
import requests

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

# OpenAI API configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
VISION_MODEL = os.environ.get('VISION_MODEL', 'gpt-4o')
VISION_API_URL = 'https://api.openai.com/v1/chat/completions'

MAX_RETRIES = 2


def analyze_image(image_s3: str) -> Dict[str, Any]:
    """Send image to Vision API for analysis with OpenAI"""
    try:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found in environment variables")
            return {}
            
        logger.info(f"Calling OpenAI Vision API for {image_s3}")
        
        # In a production environment, you'd download the image from S3
        # For now, we'll simulate having the image content
        # In the real implementation this would be the actual image data from S3
        import base64
        
        # Use a sample chart image or generate one with chart_utils
        from chart_utils import generate_chart_bytes
        # Extract symbol from s3_path (format: charts/SYMBOL/filename.png)
        try:
            symbol = image_s3.split('/')[1]
        except:
            symbol = "EUR_USD"  # Default if parsing fails
            
        image_bytes = generate_chart_bytes(symbol)
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Build request for OpenAI API
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Construct a detailed prompt for the vision model
        system_prompt = """You are an expert forex trading analyst. Analyze this chart and identify trading opportunities. 
        If you see a clear buy or sell signal, respond with action: BUY_NOW or SELL_NOW. 
        If you see a potential future setup forming, use action: ANTICIPATED_LONG or ANTICIPATED_SHORT.
        Always include entry price, stop loss (sl), take profit (tp) levels, and confidence score (0-1).
        Format your response as a valid JSON object with the following fields only:
        {"action": "BUY_NOW|SELL_NOW|ANTICIPATED_LONG|ANTICIPATED_SHORT", "entry": float, "sl": float, "tp": float, "confidence": float}
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
                            "text": f"Analyze this {symbol} forex chart and identify any trading opportunities. Look for key support/resistance levels, trend direction, and technical patterns. Consider price action around EMAs, RSI, MACD, and ATR indicators."
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
        logger.error(f"Error analyzing image {image_s3}: {str(e)}")
        return {}


def process_vision_queue():
    """Process items from the Redis 'vision_queue' and push to 'signal_queue'."""
    if not redis_client:
        logger.error("Redis client not available, cannot process vision queue")
        return

    while True:
        try:
            # Pop item from vision_queue
            item = redis_client.blpop('vision_queue', timeout=1)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Vision Worker…")
    process_vision_queue()
