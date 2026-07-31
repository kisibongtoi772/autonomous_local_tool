"""
Scheduler — manages timed & recurring workflow executions using the `schedule` library.
Schedules are persisted in workspace/schedules.json.
"""
import json
import os
import threading
import time
from typing import Callable, List, Dict, Any
import schedule as sched

from ..utils.config import SCHEDULES_FILE
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowScheduler:
    """Manages scheduled jobs that run workflows at specified intervals."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._jobs: List[Dict[str, Any]] = []
        self._play_callback: Callable | None = None
        self.load()

    def set_play_callback(self, callback: Callable):
        """Set the callback function (usually Player().play) to execute a workflow."""
        self._play_callback = callback

    def load(self):
        """Load schedules from disk."""
        if os.path.exists(SCHEDULES_FILE):
            try:
                with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
                logger.info(f"Loaded {len(self._jobs)} schedule(s).")
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")
                self._jobs = []
        else:
            self._jobs = []

    def save(self):
        """Persist schedules to disk."""
        try:
            with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._jobs)

    def add(self, workflow_file: str, interval_type: str, interval_value: Any, label: str = "") -> Dict:
        """
        Add a new schedule.
        interval_type: 'minutes' | 'hours' | 'daily_at' (HH:MM)
        interval_value: int for minutes/hours, str "HH:MM" for daily_at
        """
        job = {
            "id": int(time.time() * 1000),
            "workflow_file": workflow_file,
            "interval_type": interval_type,
            "interval_value": interval_value,
            "label": label or f"{workflow_file} every {interval_value} {interval_type}",
            "enabled": True,
            "run_count": 0,
            "last_run": None,
        }
        self._jobs.append(job)
        self.save()
        self._register_job(job)
        logger.info(f"Scheduled: {job['label']}")
        return job

    def remove(self, job_id: int):
        """Remove a schedule by ID and cancel any pending triggers."""
        self._jobs = [j for j in self._jobs if j["id"] != job_id]
        self.save()
        # Rebuild all schedules from scratch (simplest approach)
        sched.clear()
        for job in self._jobs:
            if job.get("enabled"):
                self._register_job(job)
        logger.info(f"Removed schedule id={job_id}")

    def _register_job(self, job: Dict):
        """Register a job with the schedule library."""
        if not self._play_callback:
            return

        def task():
            logger.info(f"Scheduler: running '{job['label']}'...")
            try:
                job["run_count"] = job.get("run_count", 0) + 1
                job["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.save()
                self._play_callback(job["workflow_file"])
            except Exception as e:
                logger.error(f"Scheduler error for '{job['label']}': {e}")

        iv = job["interval_type"]
        val = job["interval_value"]
        if iv == "minutes":
            sched.every(int(val)).minutes.do(task)
        elif iv == "hours":
            sched.every(int(val)).hours.do(task)
        elif iv == "daily_at":
            sched.every().day.at(str(val)).do(task)

    def start(self):
        """Start the background scheduler thread."""
        if self._running:
            return
        sched.clear()
        for job in self._jobs:
            if job.get("enabled"):
                self._register_job(job)

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SchedulerThread")
        self._thread.start()
        logger.info("Scheduler started.")

    def stop(self):
        self._running = False
        sched.clear()
        logger.info("Scheduler stopped.")

    def _run_loop(self):
        while self._running:
            sched.run_pending()
            time.sleep(1)
