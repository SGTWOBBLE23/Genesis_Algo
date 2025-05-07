import os
import logging
from datetime import datetime
from typing import List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import capture_job
from config import ASSETS              # 👈 unified list

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
#  Job wrappers
# ────────────────────────────────────────────────────────────────
def capture_all_assets() -> None:
    """Capture 15-minute charts (M15) for every configured asset."""
    logger.info("Running M15 capture for %d assets", len(ASSETS))
    for symbol in ASSETS:
        try:
            logger.info("Capturing %s (M15)", symbol)
            capture_job.run(symbol, timeframe="M15")   # ← key change
        except Exception as exc:
            logger.error("Error capturing %s (M15): %s", symbol, exc)


def capture_hourly_assets() -> None:
    """Capture hourly charts (H1) for every configured asset."""
    logger.info("Running H1 capture for %d assets", len(ASSETS))
    for symbol in ASSETS:
        try:
            logger.info("Capturing %s (H1)", symbol)
            capture_job.run(symbol, timeframe="H1")    # ← key change
        except Exception as exc:
            logger.error("Error capturing %s (H1): %s", symbol, exc)


# ────────────────────────────────────────────────────────────────
#  Scheduler setup
# ────────────────────────────────────────────────────────────────
def start_scheduler() -> BackgroundScheduler:
    """Create and start the background scheduler with two cron jobs."""
    scheduler = BackgroundScheduler()

    # Every 15 minutes at ss = 10  (00:10, 15:10, 30:10, 45:10)
    scheduler.add_job(
        capture_all_assets,
        CronTrigger(second=10, minute="*/15"),
        id="capture_15m",
        name="Capture all assets every 15 min (+10 s buffer)",
        replace_existing=True,
    )

    # Hourly at HH:00:10
    scheduler.add_job(
        capture_hourly_assets,
        CronTrigger(second=10, minute="0"),
        id="capture_1h",
        name="Capture all assets hourly (+10 s buffer)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started (15-minute & hourly jobs)")
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