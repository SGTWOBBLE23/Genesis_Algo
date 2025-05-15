import time
import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz                                       # NEW
import ml.train_models as train_models

import capture_job
from config import ASSETS              # 👈 unified list

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────
#  Job wrappers – chart captures
# ────────────────────────────────────────────────────────────────
def capture_all_assets() -> None:
    """Capture 15-minute charts (M15) for every configured asset."""
    logger.info("Running M15 capture for %d assets", len(ASSETS))
    for symbol in ASSETS:
        try:
            logger.info("Capturing %s (M15)", symbol)
            capture_job.run(symbol, timeframe="M15")
        except Exception as exc:
            logger.error("Error capturing %s (M15): %s", symbol, exc)


def capture_hourly_assets() -> None:
    """Capture hourly charts (H1) for every configured asset."""
    logger.info("Running H1 capture for %d assets", len(ASSETS))
    for symbol in ASSETS:
        try:
            logger.info("Capturing %s (H1)", symbol)
            capture_job.run(symbol, timeframe="H1")
        except Exception as exc:
            logger.error("Error capturing %s (H1): %s", symbol, exc)


# ────────────────────────────────────────────────────────────────
#  Weekly ML-retrain job
# ────────────────────────────────────────────────────────────────
PY = sys.executable  # full path to current interpreter
RETRAIN_CMDS = [
    [PY, "-m", "ml.train_rr",   "--tf", "M15", "--window", "60"],
    [PY, "-m", "ml.train_rr",   "--tf", "H1",  "--window", "180"],
    [PY, "-m", "ml.train_exit", "--tf", "M15"],
    [PY, "-m", "ml.train_exit", "--tf", "H1"],
]

_log_dir = Path(__file__).resolve().parent / "logs"
_log_dir.mkdir(exist_ok=True)
_retrain_log = _log_dir / "ml_retrain.log"

ml_logger = logging.getLogger("ml_retrain")
ml_logger.setLevel(logging.INFO)
ml_logger.addHandler(logging.FileHandler(_retrain_log))

def retrain_job() -> None:
    """Run all four training commands; stop on first failure."""
    ml_logger.info("=" * 60)
    ml_logger.info("Weekly retrain started")
    for cmd in RETRAIN_CMDS:
        ml_logger.info("▶ %s", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            ml_logger.info("✔ success\n%s", res.stdout)
        else:
            ml_logger.error(
                "✖ failed (%s)\nstdout:\n%s\nstderr:\n%s",
                res.returncode, res.stdout, res.stderr
            )
            # Abort remaining steps; APScheduler will log the traceback
            raise RuntimeError("Retrain step failed")
    ml_logger.info("Weekly retrain completed OK")


# ────────────────────────────────────────────────────────────────
#  Scheduler setup
# ────────────────────────────────────────────────────────────────
def start_scheduler() -> BackgroundScheduler:
    """Create and start the background scheduler with cron jobs."""
    scheduler = BackgroundScheduler()

    # Every 15 minutes at ss = 10  (00:10, 15:10, 30:10, 45:10)
    scheduler.add_job(
        capture_all_assets,
        CronTrigger(second=10, minute="*/15"),
        id="capture_15m",
        name="Capture all assets every 15 min (+10 s buffer)",
        replace_existing=True,
    )
    
    # Add the trade exit monitor job to run every 15 minutes
    # Import here to avoid circular imports
    try:
        from create_exit_monitor import monitor_trades_and_apply_exit_system
        scheduler.add_job(
            monitor_trades_and_apply_exit_system,
            CronTrigger(second=40, minute="*/15"),  # Run 30 seconds after capture job
            id="exit_monitor",
            name="Monitor trades for exit signals every 15 minutes",
            replace_existing=True,
        )
        logger.info("Added exit monitor job to scheduler")
    except Exception as e:
        logger.error(f"Failed to add exit monitor job: {e}")

    # Hourly at HH:00:10
    scheduler.add_job(
        capture_hourly_assets,
        CronTrigger(second=10, minute=0),
        id="capture_1h",
        name="Capture all assets hourly (+10 s buffer)",
        replace_existing=True,
    )

    # Weekly ML retrain – Sunday 23:00 UTC  (≈ 13:00 HST)
    scheduler.add_job(
        retrain_job,
        CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=pytz.UTC),
        id="weekly_ml_retrain",
        name="Weekly ML retrain",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started (15-minute, hourly, weekly jobs)")
    return scheduler


# ────────────────────────────────────────────────────────────────
#  CLI entry-point (run locally for a quick smoke test)
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sched = start_scheduler()

    try:
        # Manual smoke-test
        logger.info("Running one immediate M15 capture")
        capture_all_assets()

        # Keep the process alive so APScheduler’s background threads keep running
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
