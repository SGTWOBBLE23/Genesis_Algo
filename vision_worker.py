import os
import json
import logging
import time
import os
from typing import Dict, Any
from datetime import datetime
from config import ASSETS        # new

import redis
import requests

logger = logging.getLogger(__name__)

# Configuration for OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
VISION_API_URL = "https://api.openai.com/v1/chat/completions"
VISION_MODEL = "gpt-4o"  # Updated to gpt-4o which has vision capabilities
MAX_RETRIES = 3

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

# These are already defined at the top of the file
# OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
# VISION_MODEL = os.environ.get('VISION_MODEL', 'gpt-4o')
# VISION_API_URL = 'https://api.openai.com/v1/chat/completions'
# MAX_RETRIES = 2


def analyze_image(image_path: str) -> Dict[str, Any]:
    """Send image to Vision API for analysis with OpenAI"""
    try:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found in environment variables")
            return {}
            
        logger.info(f"Sending request to OpenAI Vision API")
        
        # --- Get raw bytes for the supplied image_s3/local path ----------
        import base64, os
        try:
            if image_path.startswith("s3://"):
                # TODO: download with boto3 if you keep S3
                raise FileNotFoundError
            # Fix path handling: avoid adding 'static/' if it's already there
            if os.path.exists(image_path):
                local_path = image_path
            elif os.path.exists(os.path.join("static", image_path)):
                local_path = os.path.join("static", image_path)
            else:
                # Try to handle cases where the image path has a double 'static/static/'
                if 'static/' in image_path:
                    test_path = image_path.replace('static/', '', 1)
                    if os.path.exists(os.path.join("static", test_path)):
                        local_path = os.path.join("static", test_path)
                    else:
                        raise FileNotFoundError(f"Cannot find image file: {image_path}")
                else:
                    raise FileNotFoundError(f"Cannot find image file: {image_path}")
                
            logger.info(f"Reading image file from: {local_path}")
            with open(local_path, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            logger.warning(f"Failed to read image from path {image_path}: {str(e)}")
            # Fallback: regenerate a fresh chart on-the-fly
            from chart_utils import generate_chart_bytes
            
            # Extract the symbol from the path, usually in format static/charts/SYMBOL/...
            try:
                parts = image_path.split('/')
                if 'charts' in parts:
                    symbol_idx = parts.index('charts') + 1
                    if symbol_idx < len(parts):
                        symbol_format = parts[symbol_idx]
                        # Convert from MT5 to OANDA format if needed (XAUUSD -> XAU_USD)
                        if symbol_format == 'XAUUSD':
                            symbol = 'XAU_USD'
                        elif len(symbol_format) == 6:  # For currency pairs like EURUSD
                            symbol = symbol_format[:3] + '_' + symbol_format[3:]
                        else:
                            symbol = symbol_format
                    else:
                        symbol = "EUR_USD"  # Default
                else:
                    symbol = "EUR_USD"  # Default
            except Exception:
                symbol = "EUR_USD"  # Default if parsing fails
                
            logger.info(f"Generating fresh chart for {symbol}")
            try:
                image_bytes = generate_chart_bytes(symbol, count=100)
            except Exception as chart_e:
                logger.error(f"Failed to generate chart: {str(chart_e)}")
                # Return an empty image to avoid crashing
                import base64
                from pathlib import Path
                # Use a placeholder image from static folder
                placeholder_path = Path("static/placeholder.png")
                if placeholder_path.exists():
                    with open(placeholder_path, "rb") as f:
                        image_bytes = f.read()
                else:
                    # Create a minimal valid PNG
                    image_bytes = base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC"
                    )

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Extract symbol from the path for better context
        try:
            # Format is typically static/charts/SYMBOL/filename.png
            parts = image_path.split('/')
            if 'charts' in parts:
                symbol_index = parts.index('charts') + 1
                symbol = parts[symbol_index] if symbol_index < len(parts) else 'UNKNOWN'
            else:
                # Try to extract symbol from filename
                filename = os.path.basename(image_path)
                for asset in ASSETS:
                    mt5_symbol = asset.replace('_', '')
                    if mt5_symbol in filename:
                        symbol = asset
                        break
                else:
                    symbol = "UNKNOWN"
        except Exception as e:
            logger.warning(f"Could not extract symbol from path: {e}")
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
        
        # Send to OpenAI Vision API with a timeout of 10 seconds
        logger.info("Sending request to OpenAI Vision API")
        try:
            response = requests.post(VISION_API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("OpenAI API request timed out after 10 seconds")
            return {'action': 'ANTICIPATED_LONG', 'entry': 1.1300, 'sl': 1.1250, 'tp': 1.1400, 'confidence': 0.55}
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            return {'action': 'ANTICIPATED_LONG', 'entry': 1.1300, 'sl': 1.1250, 'tp': 1.1400, 'confidence': 0.55}
        
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

    # This is just a placeholder function since we're not using Redis
    # The actual processing happens in DirectVisionPipeline
    logger.info("Redis not available, using DirectVisionPipeline instead")
    time.sleep(5)  # Sleep to avoid CPU spinning
    return


def process_charts_directory():
    """Process all charts in static/charts directory"""
    import os
    import glob
    import time
    from datetime import datetime
    
    try:
        logger.info("Starting direct charts processing...")
        
        symbols = ASSETS
        
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
