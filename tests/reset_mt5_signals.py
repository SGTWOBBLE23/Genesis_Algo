import os
import json
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_mt5_signals():
    """Send a reset signal request to MT5 to get all current signals"""
    
    url = "http://localhost:5000/mt5/get_signals"
    data = {
        "account_id": "163499",  # Use the account ID from the logs
        "last_signal_id": 0,
        "reset_signals": True,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            signals_count = len(result.get("signals", []))
            print(f"Successfully sent reset signal request. Got {signals_count} signals.")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"Error sending reset signal request: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Exception sending reset signal request: {str(e)}")
        return False

if __name__ == "__main__":
    reset_mt5_signals()
