"""Optional background jobs for periodic FinTrack maintenance."""

import os


def start_scheduler():
    if os.getenv("ENABLE_SCHEDULER", "").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(lambda: None, "cron", day=1, hour=0, id="monthly-score-placeholder", replace_existing=True)
    scheduler.start()
    return scheduler
