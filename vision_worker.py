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
    """Send image to Vision API for analysis (simulated for now)"""
    try:
        # In a real implementation, we would:
        # 1. Download the image from S3 or generate a pre‑signed URL
        # 2. Send to OpenAI Vision API
        # 3. Parse the response

        # --- Simulated call -------------------------------------------------
        logger.info(f"Simulating Vision API call for {image_s3}")
        simulated_response = {
            'action': 'BUY_NOW',
            'entry': 1.13005,
            'sl': 1.12750,
            'tp': 1.13500,
            'confidence': 0.85
        }
        return simulated_response
        # -------------------------------------------------------------------

        # ↳ Real‑world code (commented out)
        # headers = {
        #     'Authorization': f'Bearer {OPENAI_API_KEY}',
        #     'Content-Type': 'application/json'
        # }
        # payload = {...}
        # response = requests.post(VISION_API_URL, headers=headers, json=payload)
        # response.raise_for_status()
        # return response.json()

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
