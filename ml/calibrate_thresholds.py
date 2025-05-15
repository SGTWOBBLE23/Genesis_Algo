"""
Per-symbol threshold calibrator
───────────────────────────────
• Runs offline once a week, after model retrain.
• Pulls the last N days of live signals + final P/L from DB.
• Computes the technical-score cut-off that maximises expected net-profit
  (or F1-score, precision, etc.) for *each* symbol.
• Writes result to   config/symbol_thresholds.json
"""

import json, math, logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text
from app import app, db, Signal, Trade        
from signal_scoring import SignalScorer 


LOG = logging.getLogger("threshold_calibrator")
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config"
OUTFILE      = CONFIG_PATH / "symbol_thresholds.json"
LOOKBACK_DAYS = 30              # tunable

# ─── 1) Fetch labelled data ──────────────────────────────────────────────
def fetch_history(days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    since = datetime.utcnow() - timedelta(days=days)
    sql = text("""
        SELECT s.id, s.symbol,
               t.profit_points AS pnl,
               s.raw_payload                 -- whatever column stores the
                                            -- original JSON/fields you need
        FROM signals AS s
        JOIN trades  AS t ON t.signal_id = s.id
        WHERE s.created_at >= :since
    """)
    raw = pd.read_sql(sql, db.engine, params={"since": since})
    tech_scores = []
    for _, row in raw.iterrows():
        sig_obj = Signal.from_json(row["raw_payload"])   # or however you rebuild
        score, _ = scorer.score_signal(sig_obj)
        tech_scores.append(score)

    raw["technical_score"] = tech_scores
    return raw

# ─── 2) Calibrate one symbol ─────────────────────────────────────────────
def best_threshold(df_sym: pd.DataFrame) -> float:
    """
    Iterate possible cut-offs; choose the one with the highest
    expected net-profit per trade (or any metric you prefer).
    """
    if df_sym.empty:           # not enough data – keep global default
        return math.nan

    # Sort unique scores descending so we test realistic cut-offs only
    candidates = sorted(df_sym["technical_score"].unique(), reverse=True)

    best_cut, best_metric = None, -9e9
    for cut in candidates:
        kept   = df_sym[df_sym["technical_score"] >= cut]
        metric = kept["pnl"].sum() / len(kept)   # profit / trade
        if metric > best_metric and len(kept) >= 20:   # min sample guard
            best_cut, best_metric = cut, metric
    return round(best_cut, 4) if best_cut else math.nan

# ─── 3) Main entry point ─────────────────────────────────────────────────
def main() -> None:
    with app.app_context():        # <-- NEW: open Flask context
        LOG.info("Calibrating thresholds from last %d days", LOOKBACK_DAYS)
        df = fetch_history()
        if df.empty:
            LOG.warning("No data – skipping calibration")
            return

        out = {"default": 0.60, "overrides": {}}
    
        for sym, grp in df.groupby("symbol"):
            cut = best_threshold(grp)
            if math.isnan(cut):
                LOG.info("%s: not enough data – keep default", sym)
                continue
            out["overrides"][sym] = cut
            LOG.info("%s: best cut-off %.2f (trades=%d)",
                     sym, cut, len(grp))

    CONFIG_PATH.mkdir(exist_ok=True)
    with open(OUTFILE, "w") as fh:
        json.dump(out, fh, indent=2)
    LOG.info("→ wrote %s", OUTFILE)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
