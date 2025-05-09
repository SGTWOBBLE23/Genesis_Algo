"""
GENESIS-DEV - Trade logging helper (entry + exit → CSV + Postgres)

Changes 2025-05-08 b:
• switched deprecated Engine.has_table → inspect(engine).has_table
• removed deprecated MetaData(bind=…) pattern
• added missing import: inspect
No other logic touched.
"""

from __future__ import annotations

import os
import csv
import uuid
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import (
    Table, Column, String, DateTime, Float, Integer, MetaData, inspect
)

# Re-use the existing SQLAlchemy instance from the app
from app import db

LOGGER   = logging.getLogger(__name__)
CSV_PATH = os.path.join("logs", "trade_log.csv")


class TradeLogger:
    """Facade:  log_entry() + log_exit()  (non-blocking)."""

    def __init__(self, log_path: str = CSV_PATH) -> None:
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #
    def log_entry(self, trade_obj) -> None:
        payload = self._build_payload(trade_obj, is_exit=False)
        self._write(payload)

    def log_exit(self, trade_obj) -> None:
        payload = self._build_payload(trade_obj, is_exit=True)
        self._write(payload)

    # ------------------------------------------------------------------ #
    #  Internals
    # ------------------------------------------------------------------ #
    def _build_payload(self, t, *, is_exit: bool) -> dict:
        log_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{t.ticket}")

        payload = {
            "id":            str(log_id),
            "timestamp":     t.opened_at or datetime.utcnow(),
            "symbol":        t.symbol,
            "timeframe":     t.context.get("timeframe") if t.context else None,
            "action":        t.context.get("action") if t.context else None,
            "entry":         t.entry,
            "sl":            t.sl,
            "tp":            t.tp,
            "confidence":    t.context.get("confidence") if t.context else None,
            "chart_id":      t.context.get("chart_id") if t.context else None,
            "result":        None,
            "exit_price":    None,
            "exit_time":     None,
            "duration_sec":  None,
            "max_drawdown":  None,
            "max_favorable": None,
        }

        if is_exit:
            payload["exit_price"]   = t.exit
            payload["exit_time"]    = t.closed_at or datetime.utcnow()
            payload["duration_sec"] = (
                (payload["exit_time"] - payload["timestamp"]).total_seconds()
                if payload["exit_time"] and payload["timestamp"] else None
            )
            if t.pnl is not None:
                payload["result"] = (
                    "WIN" if t.pnl > 0 else
                    "LOSS" if t.pnl < 0 else
                    "BREAKEVEN"
                )
        return payload

    # ----------------------- writers ---------------------------------- #
    def _write(self, row: dict) -> None:
        """Append → CSV  and  upsert → Postgres (never raise)."""
        try:
            self._append_csv(row)
            self._upsert_sql(row)
        except Exception as exc:                       # pragma: no cover
            LOGGER.error("TradeLogger failure: %s", exc, exc_info=True)

    def _append_csv(self, row: dict) -> None:
        header_needed = not os.path.exists(self.log_path)
        with open(self.log_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header_needed:
                writer.writeheader()
            writer.writerow(row)

    def _upsert_sql(self, row: dict) -> None:
        """Create table on first run; thereafter use fast upsert."""
        inspector = inspect(db.engine)
        metadata  = MetaData()

        # Create the table once if it doesn't exist (use inspector, not Engine.has_table)
        if not inspector.has_table("trade_logs"):
            Table(
                "trade_logs",
                metadata,
                Column("id",            String, primary_key=True),
                Column("timestamp",     DateTime),
                Column("symbol",        String),
                Column("timeframe",     String),
                Column("action",        String),
                Column("entry",         Float),
                Column("sl",            Float),
                Column("tp",            Float),
                Column("confidence",    Float),
                Column("result",        String),
                Column("exit_price",    Float),
                Column("exit_time",     DateTime),
                Column("duration_sec",  Integer),
                Column("max_drawdown",  Float),
                Column("max_favorable", Float),
                Column("chart_id",      String),
            )
            #metadata.create_all(db.engine)
            pass

        # Reflect the existing trade_logs table
        metadata.reflect(bind=db.engine, only=["trade_logs"])
        trade_logs = metadata.tables["trade_logs"]

        stmt = insert(trade_logs).values(**row)

        # On conflict (same id) update only the exit-side columns
        update_cols = {
            k: stmt.excluded[k]
            for k in ("result", "exit_price", "exit_time",
                      "duration_sec", "max_drawdown", "max_favorable")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_cols
        )

        with db.engine.begin() as conn:
            conn.execute(stmt)
