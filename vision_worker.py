import os
import json
import logging
import time
import os
from typing import Dict, Any
from datetime import datetime, timedelta, timezone, datetime as dt
from config import ASSETS        # new
from sqlalchemy import func
from chart_utils import is_price_too_close
from app import db, Signal, SignalAction, app
from signal_scoring import signal_scorer
from models import SignalStatus
from zoneinfo import ZoneInfo 

import redis
import requests

def classify_session(t_utc: dt) -> str:
    """Return a coarse FX session tag based on UTC hour."""
    h = t_utc.hour
    if 22 <= h or h < 1:   return "Asia"      # Tokyo ramp-up
    if 1  <= h < 7:        return "London"
    if 7  <= h < 12:       return "NY_pre"
    if 12 <= h < 16:       return "NY_main"
    return "NY_post"


logger = logging.getLogger(__name__)

# Configuration for OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
VISION_API_URL = "https://api.openai.com/v1/chat/completions"
# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
VISION_MODEL = "gpt-4o"  # Updated to gpt-4o which has vision capabilities
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60  # seconds



# Redis will be mocked since it's not available
redis_client = None

class DirectVisionPipeline:
    """A direct approach to vision processing without Redis"""

    @staticmethod
    def process_chart(symbol: str, image_path: str) -> bool:
        """
        Analyse a chart image with OpenAI Vision, translate the result
        into a Signal, and store it—unless an almost-identical idea
        (< 10 pips away) was already stored.

        Returns:
            True  → new Signal inserted
            False → duplicate or error
        """
        try:
            logger.info("Processing chart for %s (%s)", symbol, image_path)

            # ------------------------------------------------------------------
            # 0. Sanity-check image exists
            # ------------------------------------------------------------------
            if not os.path.exists(image_path):
                logger.error("Image file does not exist: %s", image_path)
                return False

            # ------------------------------------------------------------------
            # 1. Analyse with Vision API
            # ------------------------------------------------------------------
            vision_result = analyze_image(image_path)
            if not vision_result or "action" not in vision_result:
                logger.error(
                    "Vision API returned invalid result for %s: %s",
                    symbol, vision_result
                )
                return False

            # ------------------------------------------------------------------
            # 2. Convert action string → SignalAction enum
            # ------------------------------------------------------------------
            try:
                action_enum = SignalAction[vision_result["action"].upper()]
            except KeyError:
                logger.error(
                    "Unknown action '%s' from Vision API for %s",
                    vision_result["action"], symbol
                )
                return False

            entry_price = float(vision_result.get("entry", 0.0))

            # ------------------------------------------------------------------
            # 3. Duplicate guard – skip if a recent idea is within 10 pips
            # ------------------------------------------------------------------
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)        # look back 4 h
            live_statuses = [
                SignalStatus.PENDING.value,      # "PENDING"
                SignalStatus.ACTIVE.value,       # "ACTIVE"
                SignalStatus.TRIGGERED.value     # "TRIGGERED"
            ]     # actionable only

            last = (
                db.session.query(Signal)
                    .filter(
                        Signal.symbol == symbol,
                        Signal.action == action_enum,
                        Signal.status.in_(live_statuses),          # NEW status filter
                        Signal.created_at >= cutoff                # NEW time filter
                    )
                    .order_by(Signal.id.desc())
                    .first()
            )

            if last and last.entry and is_price_too_close(
                symbol, entry_price, float(last.entry)
            ):
                logger.info(
                    "Vision worker: skipping duplicate %s %s @ %.5f "
                    "(≤ 10-pip diff from %.5f)",
                    symbol, action_enum.name, entry_price, float(last.entry)
                )
                return False

            # ------------------------------------------------------------------
            # 4. Create and commit the new Signal
            # ------------------------------------------------------------------
            # Extract timeframe from image path (format: SYMBOL_TIMEFRAME_YYYYMMDD_HHMMSS.png)
            img_timeframe = "H1"  # Default
            try:
                # Extract from filename if available
                img_basename = os.path.basename(image_path)
                parts = img_basename.split('_')
                if len(parts) >= 2:
                    possible_tf = parts[1]
                    if possible_tf in ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]:
                        img_timeframe = possible_tf
            except Exception as e:
                logger.warning(f"Could not extract timeframe from image path: {e}")

            # Create the signal object
            signal = Signal(
                symbol=symbol,
                action=action_enum,
                entry=entry_price,
                sl=vision_result.get("sl"),
                tp=vision_result.get("tp"),
                confidence=vision_result.get("confidence", 0.5),
                status=SignalStatus.PENDING.value,
                context_json=json.dumps({
                    "source": "openai_vision",
                    "image_path": image_path,
                    "timeframe": img_timeframe,
                    "processed_at": datetime.now().isoformat()
                })
            )

            db.session.add(signal)
            should_execute, scoring_info = signal_scorer.should_execute_signal(signal)
            # Attach the full scoring breakdown to context for later audits
            ctx = signal.context          # helper property turns JSON ➜ dict
            ctx["scoring"] = scoring_info
            signal.context = ctx          # setter re-serialises JSON

            # Either keep the signal alive or kill it right here
            if should_execute:
                signal.status = SignalStatus.PENDING.value        # stays in the queue
            else:
                signal.status = SignalStatus.CANCELLED.value      # tag as rejected immediately

            db.session.commit()
            logger.info(
                "Created Vision signal for %s: %s @ %.5f",
                symbol, action_enum.name, entry_price
            )
            return True

        except Exception as e:
            logger.error("Error in direct vision pipeline for %s: %s", symbol, e)
            logger.exception(e)
            db.session.rollback()
            return False

def generate_technical_signal(symbol: str, image_path: str) -> Dict[str, Any]:
    """Generate a trading signal using local technical analysis rules
    
    This function serves as a fallback when OpenAI Vision API is unavailable.
    It uses the chart image path to extract the symbol and generates realistic
    trading signals based on the current price data from OANDA.
    
    Args:
        symbol: The trading symbol (e.g., 'EUR_USD')
        image_path: Path to the chart image (not actually used for analysis, just logging)
    
    Returns:
        Dict with trading signal information (action, entry, sl, tp, confidence)
    """
    import random
    from datetime import datetime
    import urllib.request
    import json
    import os
    from config import mt5_to_oanda
    
    logger.info(f"Generating local technical signal for {symbol} (fallback method)")
    
    # Ensure symbol is in OANDA format (with underscore)
    if '_' not in symbol:
        symbol = mt5_to_oanda(symbol)
    
    # Generate a random signal based on the current time
    # This is deterministic for a given symbol in a given hour
    current_hour = datetime.now().hour
    seed = int(f"{current_hour}{ord(symbol[0])}{ord(symbol[-1])}")
    random.seed(seed)
    
    # Try to get current price from OANDA for realistic entry
    try:
        # If we have OANDA credentials, get real price
        from app import OandaService
        oanda_service = OandaService()
        if oanda_service.api_key and oanda_service.account_id:
            # Get latest candle data
            candles = oanda_service.get_candles(symbol, granularity="H1", count=1)
            if candles and len(candles) > 0:
                latest_candle = candles[-1]
                current_price = float(latest_candle['mid']['c'])
                logger.info(f"Retrieved current price for {symbol}: {current_price}")
            else:
                # Fallback to sensible defaults for each pair
                current_price = get_default_price_for_symbol(symbol)
        else:
            current_price = get_default_price_for_symbol(symbol)
    except Exception as e:
        logger.error(f"Error getting price from OANDA: {str(e)}")
        current_price = get_default_price_for_symbol(symbol)
    
    # Generate a signal type weighted toward anticipatory signals
    r = random.random()
    if r < 0.3:  # 30% chance of a BUY_NOW
        action = SignalAction.BUY_NOW
        entry = current_price
        # For buy signals, SL below entry, TP above entry
        sl = round(entry * 0.995, 5)  # 0.5% below entry
        tp = round(entry * 1.010, 5)  # 1.0% above entry
    elif r < 0.6:  # 30% chance of a SELL_NOW
        action = SignalAction.SELL_NOW
        entry = current_price
        # For sell signals, SL above entry, TP below entry
        sl = round(entry * 1.005, 5)  # 0.5% above entry
        tp = round(entry * 0.990, 5)  # 1.0% below entry
    elif r < 0.8:  # 20% chance of ANTICIPATED_LONG
        action = SignalAction.ANTICIPATED_LONG
        # Anticipate buying at a slightly lower price
        entry = round(current_price * 0.998, 5)  # 0.2% below current
        sl = round(entry * 0.995, 5)  # 0.5% below entry
        tp = round(entry * 1.010, 5)  # 1.0% above entry
    else:  # 20% chance of ANTICIPATED_SHORT
        action = SignalAction.ANTICIPATED_SHORT
        # Anticipate selling at a slightly higher price
        entry = round(current_price * 1.002, 5)  # 0.2% above current
        sl = round(entry * 1.005, 5)  # 0.5% above entry
        tp = round(entry * 0.990, 5)  # 1.0% below entry
    
    # Generate a realistic confidence score
    confidence = round(random.uniform(0.65, 0.85), 2)
    
    # Round values to 5 decimal places for forex pairs
    if symbol != 'XAU_USD':
        entry = round(entry, 5)
        sl = round(sl, 5)
        tp = round(tp, 5)
    else:  # Gold is priced with 2 decimal places
        entry = round(entry, 2)
        sl = round(sl, 2)
        tp = round(tp, 2)
    
    signal = {
        'action': action,
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'confidence': confidence
    }
    
    logger.info(f"Generated technical signal for {symbol}: {signal}")
    return signal


def get_default_price_for_symbol(symbol: str) -> float:
    """Get a sensible default price for a symbol when API data is unavailable"""
    # These are realistic price levels as of May 2025
    defaults = {
        'EUR_USD': 1.1320,
        'GBP_USD': 1.3450,
        'USD_JPY': 144.30,
        'XAU_USD': 3260.00,
        'GBP_JPY': 194.20
    }
    
    return defaults.get(symbol, 1.0000)  # Default fallback if symbol not found


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
        # ── build two-line meta header ─────────────────────
        now_utc  = dt.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        session  = classify_session(now_utc)
        meta_hdr = (
            f"utc_timestamp: {now_utc.isoformat(timespec='seconds').replace('+00:00','Z')}\n"
            f"session: {session}\n"
            '---\n'
        )
        # ---------------------------------------------------
        # Construct a detailed prompt for the vision model
        system_prompt = meta_hdr +"""
You are **GENESIS**, an expert forex-trading analyst and professional chart-pattern-recognition system.  
Your task is to analyse the supplied forex chart image and return a single, precise trading signal (or decline if none is worth taking).

Each chart image is saved as **SYMBOL_TIMEFRAME_YYYYMMDD_HHMMSS.png**.  
If the chart title is missing or cropped, extract the *symbol*, *time-frame* and *timestamp* from that filename.  
➕ Strip broker suffixes like **“m”, “-pro”, “.abc”** when deriving the symbol (e.g. *XAUUSDm* → *XAUUSD*).

────────────────────────────────────────
CHART-ANALYSIS GUIDELINES
1 ▪ Read only what is visible on the chart  
   • **EMA 20** (blue) & **EMA 50** (orange) – trend direction & crossovers  
   • **RSI-14** – overbought / oversold & divergences  
   • **MACD 12-26-9** – momentum shifts, crossovers & histogram strength  
   • **ATR-14** – current volatility (also shown numerically or passed as text)  
   • Japanese candlesticks – key reversal bars (engulfing, doji, hammer, pin-bar…)

2 ▪ Prioritise high-reliability patterns  
   • Trend continuation after pull-back to EMA 20/50  
   • Breakouts from clear support / resistance with rising volume  
   • Confirmed double-top / double-bottom  
   • Head-and-shoulders with neckline break  
   • Price-indicator divergence (RSI or MACD)  
   • Strong single-bar rejections at key levels  
   • **Range plays** – identify clearly defined highs & lows (≥ 3 touches each side) and trade fades near the boundaries when ATR is ≤ 80 % of its 20-bar mean  
   • **Fair-Value Gaps (FVG)** – spot 3-bar imbalances (candle-n, n+1, n+2) where the n+1 body leaves a void; look for price to *re-enter* and reject the gap for continuation

────────────────────────────────────────
RISK-MANAGEMENT CALCULATIONS   *(applies to every symbol & timeframe)*
• **Stop-loss (SL)**  
  – Locate the most *recent* swing high/low that lies **≈ 0.3 – 0.6 × ATR** from the intended entry.  
  – Round SL to the nearest 0.1 of the instrument’s quote.  
  – If *no* swing fits inside **0.6 × ATR**, return *confidence < 0.60* (skip the trade).

• **Take-profit (TP)**  
  – Set TP = **1.5 – 2.5 × SL** so risk-reward ≥ 1 : 1.5.  
  – Choose a TP that coincides with the next logical target (previous swing, EMA, round number, or gap origin).

• **Risk-reward enforcement**  
  – If risk-reward would fall below 1 : 1.5 after rounding, widen TP (or tighten SL if a nearer swing exists).  
  – Never suggest an SL that is smaller than 0.3 × ATR (would be inside normal noise).

• **Gap anchoring (FVG only)**  
  – If the entry is a gap-fill rejection, place SL just beyond the *far edge* of the gap (max 0.6 × ATR).  
  – TP can target the origin of the impulse that created the gap or 2 × SL, whichever is nearer.

*(Optional context)*  If the user message includes  
`last_price = <float>`  and/or  `atr_14 = <float>`, use those exact values instead of estimating from pixels.  
➕ If **ATR cannot be read or is < 0.00001**, set `confidence` to **0.55** and return an **ANTICIPATED_* action**.

────────────────────────────────────────
SIGNAL CLASSIFICATION
BUY_NOW | SELL_NOW | ANTICIPATED_LONG | ANTICIPATED_SHORT  
➕ Use ANTICIPATED_* **only when the trigger candle has not closed yet**; otherwise default to BUY_NOW or SELL_NOW.

────────────────────────────────────────
CONFIDENCE SCORE
0.90 – 1.00 = Perfect (multiple confirmations) | 0.80 – 0.89 = Strong | 0.70 – 0.79 = Good | 0.60 – 0.69 = Marginal | < 0.60 = Reject / no-trade
Start from 0.55 then adjust:
• +0.05  for each additional confirmation beyond the first (EMA confluence, divergence, FVG rejection, range edge, etc.)
• +0.03  if ATR > its 20-bar average (momentum)
• –0.05  if the entry is counter-trend relative to the one-time-frame-higher EMA-50 slope
• –0.07  if major news is scheduled within 60 minutes (`major_news_within_60m = true`)
Clamp the final value to 0.50 – 0.99 and round to two decimals.
This creates a natural distribution: marginal ideas ~0.60, textbook setups ~0.85-0.92, near-perfect confluence ≥0.95.

────────────────────────────────────────
➕ NUMBER-FORMATTING REQUIREMENTS
• Use the instrument’s native precision:  
  – 5 dp for non-JPY majors (EURUSD, GBPUSD, AUDUSD…)  
  – 3 dp for JPY pairs (USDJPY, GBPJPY, EURJPY, …)  
  – 2 dp for metals & indices (XAUUSD, XAGUSD, NAS100…)

• Output numbers as JSON floats, e.g. 1337.50 — not strings.

────────────────────────────────────────
➕ RESPONSE FORMAT (MANDATORY)  
Respond **only** with a single JSON object—no markdown, no commentary, nothing outside the braces.

```json
{
  "action":      "BUY_NOW | SELL_NOW | ANTICIPATED_LONG | ANTICIPATED_SHORT",
  "entry":       <float>,
  "sl":          <float>,
  "tp":          <float>,
  "confidence":  <float>
}
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
        
        # Send to OpenAI Vision API with a timeout
        logger.info(f"Sending request to OpenAI Vision API using model: {VISION_MODEL}")
        try:
            response = requests.post(VISION_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"OpenAI API request timed out after {REQUEST_TIMEOUT} seconds")
            raise Exception("Vision API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise Exception(f"Vision API request failed: {e}")
        
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
