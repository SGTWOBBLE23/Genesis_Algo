# mt5_manager.py  ← NEW FILE
import os
import requests

class MT5Manager:
    """
    Tiny helper that forwards REST calls from Flask → MetaTrader EA.
    Keeps _all_ MT5-specific code in one place and avoids circular imports.
    """

    # EA web-server URL (set in Replit secrets / .env)
    BASE_URL = os.getenv("MT5_EA_HOST", "http://localhost:8005")

    # ------------- public helpers ---------------------------------
    @staticmethod
    def close_position(ticket: int) -> bool:
        """Close the whole position identified by <ticket>."""
        resp = requests.post(
            f"{MT5Manager.BASE_URL}/close_position",
            json={"ticket": int(ticket)},
            timeout=5,
        )
        return resp.ok

    @staticmethod
    def modify_sl_tp(ticket: int, sl: float | None = None,
                     tp: float | None = None) -> bool:
        """Move SL/TP on an open position.  Pass only what you change."""
        payload = {"ticket": int(ticket)}
        if sl is not None:
            payload["sl"] = float(sl)
        if tp is not None:
            payload["tp"] = float(tp)

        resp = requests.post(
            f"{MT5Manager.BASE_URL}/modify_sl_tp",
            json=payload,
            timeout=5,
        )
        return resp.ok

    @staticmethod
    def close_partial(ticket: int, lots: float) -> bool:
        """Close <lots> on a position without flattening it."""
        resp = requests.post(
            f"{MT5Manager.BASE_URL}/close_partial",
            json={"ticket": int(ticket), "lots": float(lots)},
            timeout=5,
        )
        return resp.ok
