from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

from .adapters import ADAPTERS
from .state import StateStore


class Scheduler:
    def __init__(self, browser, jobs, max_concurrent_jobs=12):
        self.browser = browser
        self.jobs = jobs
        self.max_concurrent_jobs = max_concurrent_jobs
        self.states = StateStore()
        self.running = False
        self.tasks = []
        self.sem = asyncio.Semaphore(max_concurrent_jobs)
        self.active_job_ids = set()

    async def run_job(self, job: dict):
        job_id = job["id"]
        state = self.states.get(job_id)
        if job_id in self.active_job_ids:
            state.last_message = "Skipped: previous cycle still running"
            return

        self.active_job_ids.add(job_id)
        state.state = "RUNNING"
        started = time.perf_counter()

        try:
            adapter = ADAPTERS.get(job["transport"])
            if not adapter:
                raise RuntimeError(f"Unsupported transport: {job['transport']}")

            async with self.sem:
                page = await self.browser.new_page()
                try:
                    result = await adapter(page, job)
                finally:
                    await page.close()

            state.state = result.get("status", "SUCCESS")
            state.download_status = result.get("status", "SUCCESS")
            state.last_message = result.get("output", result.get("validation", ""))
            state.last_error_category = ""
        except Exception as exc:
            state.state = "FAILED"
            state.error_count += 1
            state.last_error_category = type(exc).__name__
            state.last_message = str(exc)
        finally:
            state.last_run = datetime.now().isoformat(timespec="seconds")
            state.duration_seconds = round(time.perf_counter() - started, 2)
            self.active_job_ids.discard(job_id)

    async def loop(self):
        self.running = True
        last_run = {}
        while self.running:
            now = time.monotonic()
            for job in self.jobs:
                if not job.get("enabled"):
                    continue
                interval = max(1, int(job.get("interval_minutes", 5))) * 60
                if now - last_run.get(job["id"], 0) >= interval:
                    last_run[job["id"]] = now
                    asyncio.create_task(self.run_job(job))
            await asyncio.sleep(1)

    def stop(self):
        self.running = False
