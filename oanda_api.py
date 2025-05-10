import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def fetch_candles(
    instrument: str,
    granularity: str = "H1",
    count: int = 5000,
    api_key: str | None = None,
    account_id: str | None = None,
):
    """
    One-shot helper that delegates to OandaAPI.get_candles().
    Keeps backward-compat with existing capture_job import.
    """
    api = OandaAPI(api_key=api_key, account_id=account_id)
    return api.get_candles(instrument, granularity, count)

def fetch_candles(symbol: str, timeframe: str, count: int = 100, to: datetime = None) -> list:
    """Fetch historical candles for a symbol"""
    try:
        # Create API instance for the request
        api = OandaAPI(
            api_key=os.environ.get('OANDA_API_KEY'),
            account_id=os.environ.get('OANDA_ACCOUNT_ID')
        )
        
        # Build endpoint with optional 'to' parameter
        endpoint = f"/instruments/{symbol}/candles"
        params = {
            "count": count,
            "granularity": timeframe,
            "price": "M"  # Midpoint
        }
        if to:
            params["to"] = to.strftime("%Y-%m-%dT%H:%M:%SZ")
            
        response = api._make_request(endpoint, params)
        if response and 'candles' in response:
            return response['candles']
        return []
    except Exception as e:
        logger.error(f"Error fetching candles for {symbol}: {e}")
        return []

class OandaAPI:
    """Class for interacting with the OANDA REST API"""
    
    def __init__(self, api_key: Optional[str] = None, account_id: Optional[str] = None):
        api_key_value = api_key or os.environ.get("OANDA_API_KEY")
        account_id_value = account_id or os.environ.get("OANDA_ACCOUNT_ID")
        self.api_key = str(api_key_value) if api_key_value else ""
        self.account_id = str(account_id_value) if account_id_value else ""
        self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        """Make a request to the OANDA API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OANDA API request error: {str(e)}")
            return {"error": str(e)}
    
    def get_account_summary(self) -> Dict:
        """Get account summary information"""
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
            
        endpoint = f"/accounts/{self.account_id}/summary"
        return self._make_request(endpoint)
    
    def get_instruments(self) -> List[Dict]:
        """Get list of available instruments"""
        if not self.account_id or not self.api_key:
            return [{"error": "Missing account ID or API key"}]
            
        endpoint = f"/accounts/{self.account_id}/instruments"
        response = self._make_request(endpoint)
        
        if "error" in response:
            return [response]
            
        return response.get("instruments", [])
    
    def get_prices(self, instruments: List[str]) -> Dict:
        """Get current prices for specified instruments"""
        if not self.api_key:
            return {"error": "Missing API key"}
            
        endpoint = "/pricing"
        params = {
            "accountID": self.account_id,
            "instruments": ",".join(instruments)
        }
        
        return self._make_request(endpoint, params=params)
    
    def get_candles(self, instrument: str, granularity: str = "H1", count: int = 50) -> List[Dict]:
        """Get price candles for an instrument
        
        Args:
            instrument (str): Instrument name (e.g., "EUR_USD")
            granularity (str): Timeframe (e.g., "M5", "H1", "D")
            count (int): Number of candles to retrieve
        
        Returns:
            List[Dict]: List of candle data
        """
        
        if not self.api_key:
            return [{"error": "Missing API key"}]
            
        endpoint = f"/instruments/{instrument}/candles"
        params = {
            "granularity": granularity,
            "count": count
        }
        
        response = self._make_request(endpoint, params=params)
        
        if "error" in response:
            return [response]
            
        candles = []
        for candle in response.get("candles", []):
            if candle["complete"]:
                # Parse ISO timestamp from OANDA (format: "2025-05-04T12:00:00.000000Z")
                try:
                    # Convert to datetime to ensure proper timestamp handling
                    timestamp = datetime.fromisoformat(candle["time"].replace('Z', '+00:00'))
                    
                    candle_data = {
                        "timestamp": timestamp,
                        "open": float(candle["mid"]["o"]),
                        "high": float(candle["mid"]["h"]),
                        "low": float(candle["mid"]["l"]),
                        "close": float(candle["mid"]["c"]),
                        "volume": candle["volume"]
                    }
                except (ValueError, KeyError) as e:
                    logger.error(f"Error parsing candle timestamp: {e}")
                    continue
                candles.append(candle_data)
                
        return candles
    
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades for the account"""
        if not self.account_id or not self.api_key:
            return [{"error": "Missing account ID or API key"}]
            
        endpoint = f"/accounts/{self.account_id}/openTrades"
        response = self._make_request(endpoint)
        
        if "error" in response:
            return [response]
            
        return response.get("trades", [])
    
    def create_order(self, instrument: str, units: float, take_profit: Optional[float] = None, 
                     stop_loss: Optional[float] = None) -> Dict:
        """Create a new market order
        
        Args:
            instrument (str): Instrument name (e.g., "EUR_USD")
            units (float): Positive for buy, negative for sell
            take_profit (Optional[float]): Take profit price level
            stop_loss (Optional[float]): Stop loss price level
        
        Returns:
            Dict: Order response
        """
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
            
        endpoint = f"/accounts/{self.account_id}/orders"
        
        order_data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK"
            }
        }
        
        if take_profit:
            order_data["order"]["takeProfitOnFill"] = {
                "price": str(take_profit)
            }
            
        if stop_loss:
            order_data["order"]["stopLossOnFill"] = {
                "price": str(stop_loss)
            }
        
        return self._make_request(endpoint, method="POST", data=order_data)
    
    def close_trade(self, trade_id: str) -> Dict:
        """Close an open trade
        
        Args:
            trade_id (str): Trade ID to close
        
        Returns:
            Dict: Close trade response
        """
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
            
        endpoint = f"/accounts/{self.account_id}/trades/{trade_id}/close"
        return self._make_request(endpoint, method="PUT")
    
    def get_account_history(self, days: int = 30) -> Dict:
        """Get account transaction history
        
        Args:
            days (int): Number of days of history to retrieve
        
        Returns:
            Dict: Transaction history
        """
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
            
        from_time = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        endpoint = f"/accounts/{self.account_id}/transactions/sinceid"
        params = {
            "id": "1",
            "type": "ORDER_FILL"
        }
        
        return self._make_request(endpoint, params=params)
    
    def test_connection(self) -> bool:
        """Test if the API connection is working
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        if not self.account_id or not self.api_key:
            return False
            
        response = self.get_account_summary()
        return "error" not in response