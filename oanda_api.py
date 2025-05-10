"""
Light-weight OANDA REST helper.

• `fetch_candles()` is a convenience wrapper used by capture_job / back-fill.
• `OandaAPI` holds all lower-level endpoints.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Convenience wrapper (stateless)
# ──────────────────────────────────────────────────────────────
def fetch_candles(
    symbol: str,
    timeframe: str = "H1",
    count: int = 5000,
    *,
    to: datetime | None = None,
    price: str = "M",
    api_key: str | None = None,
    account_id: str | None = None,
) -> List[Dict]:
    """
    One-shot helper – identical signature to legacy `capture_job.fetch_candles`
    but now forwards **extra params** into the REST call.

    Example
    -------
    >>> candles = fetch_candles("XAU_USD", "M1", 1000,
    ...                         to=datetime.utcnow(), price="BA")
    """
    api = OandaAPI(api_key=api_key, account_id=account_id)

    params: Dict[str, str] = {"price": price}
    if to:
        params["to"] = to.strftime("%Y-%m-%dT%H:%M:%SZ")

    return api.get_candles(symbol, timeframe, count, **params)


# ──────────────────────────────────────────────────────────────
#  Low-level API class
# ──────────────────────────────────────────────────────────────
class OandaAPI:
    """Minimal OANDA v3 client (practice or live)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        practice: bool = True,
    ) -> None:
        key = api_key or os.environ.get("OANDA_API_KEY", "")
        acct = account_id or os.environ.get("OANDA_ACCOUNT_ID", "")

        self.api_key: str = str(key)
        self.account_id: str = str(acct)
        domain = "api-fxpractice" if practice else "api-fxtrade"
        self.base_url = f"https://{domain}.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ---------- generic request runner ----------
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        *,
        params: Dict | None = None,
        data: Dict | None = None,
    ) -> Dict:
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                resp = requests.get(url, headers=self.headers, params=params)
            elif method == "POST":
                resp = requests.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                resp = requests.put(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("OANDA API request error: %s", exc)
            return {"error": str(exc)}

    # ---------- market data ----------
    def get_candles(
        self,
        instrument: str,
        granularity: str = "H1",
        count: int = 50,
        **params,
    ) -> List[Dict]:
        """
        Return a *list* of dicts:

            [{
                "timestamp": datetime,
                "open":  float, "high": float,
                "low":   float, "close": float,
                "volume": int
            }, …]
        """
        if not self.api_key:
            return [{"error": "Missing API key"}]

        qs = {"granularity": granularity, "count": count, **params}
        endpoint = f"/instruments/{instrument}/candles"
        raw = self._make_request(endpoint, params=qs)

        if "error" in raw:
            return [raw]

        candles: List[Dict] = []
        for cndl in raw.get("candles", []):
            if not cndl.get("complete"):
                continue

            try:
                iso = cndl["time"]                         # keep raw ISO string
                ts  = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                candles.append(
                    {
                        "time": ts,           # ← now datetime, fixes TypeError
                        "time_iso": iso,      #   keep raw string if someone needs it
                        "timestamp": ts,      # ← nicer typed variant for new code
                        "open":  float(cndl["mid"]["o"]),
                        "high":  float(cndl["mid"]["h"]),
                        "low":   float(cndl["mid"]["l"]),
                        "close": float(cndl["mid"]["c"]),
                        "volume": cndl["volume"],
                    }
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Bad candle in %s: %s", instrument, exc)

        return candles

    # ---------- account / trade helpers ----------
    def get_account_summary(self) -> Dict:
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
        return self._make_request(f"/accounts/{self.account_id}/summary")

    def get_instruments(self) -> List[Dict]:
        if not self.account_id or not self.api_key:
            return [{"error": "Missing account ID or API key"}]
        res = self._make_request(f"/accounts/{self.account_id}/instruments")
        return res.get("instruments", []) if "error" not in res else [res]

    def get_prices(self, instruments: List[str]) -> Dict:
        if not self.api_key:
            return {"error": "Missing API key"}
        qs = {"accountID": self.account_id, "instruments": ",".join(instruments)}
        return self._make_request("/pricing", params=qs)

    def get_open_trades(self) -> List[Dict]:
        if not self.account_id or not self.api_key:
            return [{"error": "Missing account ID or API key"}]
        res = self._make_request(f"/accounts/{self.account_id}/openTrades")
        return res.get("trades", []) if "error" not in res else [res]

    # ---------- order helpers ----------
    def create_order(
        self,
        instrument: str,
        units: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Dict:
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}

        order: Dict = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
            }
        }
        if take_profit:
            order["order"]["takeProfitOnFill"] = {"price": str(take_profit)}
        if stop_loss:
            order["order"]["stopLossOnFill"] = {"price": str(stop_loss)}

        return self._make_request(
            f"/accounts/{self.account_id}/orders", method="POST", data=order
        )

    def close_trade(self, trade_id: str) -> Dict:
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
        return self._make_request(
            f"/accounts/{self.account_id}/trades/{trade_id}/close", method="PUT"
        )

    # ---------- history ----------
    def get_account_history(self, days: int = 30) -> Dict:
        if not self.account_id or not self.api_key:
            return {"error": "Missing account ID or API key"}
        _ = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        # The practice API needs a transaction-id cursor; we just fetch from 1
        return self._make_request(
            f"/accounts/{self.account_id}/transactions/sinceid",
            params={"id": "1", "type": "ORDER_FILL"},
        )

    # ---------- diagnostics ----------
    def test_connection(self) -> bool:
        return "error" not in self.get_account_summary()
