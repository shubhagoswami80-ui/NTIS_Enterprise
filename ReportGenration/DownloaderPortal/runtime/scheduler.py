from __future__ import annotations

import asyncio
import time
from datetime import datetime, date, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .adapters import ADAPTERS
from .state import StateStore

DAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def _parse_hhmm(value: str, fallback: dtime) -> dtime:
    try:
        h, m = str(value or "").strip().split(":", 1)
        return dtime(int(h), int(m))
    except Exception:
        return fallback


def _tz(job: dict):
    name = str(job.get("schedule", {}).get("timezone") or "Asia/Kolkata")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def _schedule(job: dict) -> dict:
    s = dict(job.get("schedule") or {})
    s.setdefault("enabled", bool(job.get("enabled", False)))
    s.setdefault("start_time", "09:25")
    s.setdefault("stop_time", "15:35")
    s.setdefault("recurrence_minutes", int(job.get("interval_minutes", 5) or 5))
    s.setdefault("days", ["MON", "TUE", "WED", "THU", "FRI"])
    s.setdefault("timezone", "Asia/Kolkata")
    s.setdefault("start_date", "")
    s.setdefault("end_date", "")
    s.setdefault("mode", "recurring")
    s.setdefault("overlap_policy", job.get("overlap_policy", "skip_if_previous_cycle_running"))
    return s


def normalize_job(job: dict) -> dict:
    s = _schedule(job)
    job["schedule"] = s
    job.setdefault("processing_root", "")
    job.setdefault("final_output_root", "")
    job.setdefault("browser_profile", "")
    job.setdefault("page_isolation", True)
    job.setdefault("profile_conflict_policy", "shared_context_dedicated_page")
    job.setdefault("execution_owner", "downloader_portal_9001")
    job.setdefault("scheduler_id", f"{job.get('id', 'job')}_scheduler")
    job.setdefault("location", {})
    job["enabled"] = bool(job.get("enabled", False))
    return job


def _date_ok(s: dict, now_local: datetime) -> bool:
    days = {DAYS.get(str(x).upper()) for x in s.get("days", [])}
    days.discard(None)
    if days and now_local.weekday() not in days:
        return False
    try:
        if s.get("start_date") and now_local.date() < date.fromisoformat(s["start_date"]):
            return False
        if s.get("end_date") and now_local.date() > date.fromisoformat(s["end_date"]):
            return False
    except ValueError:
        return False
    return True


def in_window(job: dict, now: datetime | None = None) -> bool:
    s = _schedule(job)
    local = (now or datetime.now(_tz(job))).astimezone(_tz(job))
    if not _date_ok(s, local):
        return False
    start = _parse_hhmm(s.get("start_time"), dtime(9, 25))
    stop = _parse_hhmm(s.get("stop_time"), dtime(15, 35))
    current = local.time().replace(tzinfo=None)
    if start <= stop:
        return start <= current <= stop
    return current >= start or current <= stop


def next_run(job: dict, after: datetime | None = None) -> datetime | None:
    s = _schedule(job)
    tz = _tz(job)
    base = (after or datetime.now(tz)).astimezone(tz)
    interval = max(1, int(s.get("recurrence_minutes", 5) or 5))
    start = _parse_hhmm(s.get("start_time"), dtime(9, 25))
    stop = _parse_hhmm(s.get("stop_time"), dtime(15, 35))
    allowed = {DAYS.get(str(x).upper()) for x in s.get("days", [])}
    allowed.discard(None)

    for day_offset in range(0, 370):
        candidate_date = (base + timedelta(days=day_offset)).date()
        if allowed and candidate_date.weekday() not in allowed:
            continue
        try:
            if s.get("start_date") and candidate_date < date.fromisoformat(s["start_date"]):
                continue
            if s.get("end_date") and candidate_date > date.fromisoformat(s["end_date"]):
                continue
        except ValueError:
            continue
        candidate = datetime.combine(candidate_date, start, tzinfo=tz)
        if candidate < base:
            elapsed = int((base - candidate).total_seconds())
            slots = (elapsed + interval * 60 - 1) // (interval * 60)
            candidate += timedelta(minutes=slots * interval)
        if candidate.time().replace(tzinfo=None) <= stop and candidate >= base:
            return candidate
    return None


class Scheduler:
    """Independent per-job scheduler. Jobs never wait on a portal-wide semaphore."""

    def __init__(self, browser, jobs, states=None):
        self.browser = browser
        self.jobs = jobs
        self.states = states or StateStore()
        self.running = False
        self.tasks: dict[str, asyncio.Task] = {}
        self.active_job_ids: set[str] = set()
        self.manual_tasks: dict[str, object] = {}
        self.active_job_meta: dict[str, dict] = {}
        self.last_completion: dict[str, str] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def refresh_jobs(self, jobs):
        self.jobs = jobs

    def _job(self, job_id):
        return next((j for j in self.jobs if j.get("id") == job_id), None)

    async def run_job(self, job: dict, manual: bool = False):
        job = normalize_job(job)
        job_id = job["id"]
        state = self.states.get(job_id)
        if job_id in self.active_job_ids:
            state.last_message = "SKIPPED: previous cycle still running"
            state.state = "SKIPPED"
            return
        if not manual and not in_window(job):
            state.state = "WAITING"
            state.next_run = _state_next(job)
            return

        self.active_job_ids.add(job_id)
        self.active_job_meta[job_id] = {
            "mode": "MANUAL" if manual else "SCHEDULED",
            "started_at": datetime.now(_tz(job)).isoformat(timespec="seconds"),
        }
        state.state = "RUNNING"
        state.download_status = "RUNNING"
        state.processing_status = "NOT_RUN"
        state.last_message = ""
        state.started_at = datetime.now(_tz(job)).isoformat(timespec="seconds")
        state.heartbeat_at = state.started_at
        state.current_stage = "STARTING"
        state.current_detail = f"Starting {job.get('transport', 'job')}"
        self.active_job_meta[job_id].update({"stage": "STARTING", "detail": state.current_detail})
        try:
            self.states.save()
        except Exception:
            pass
        started = time.perf_counter()
        heartbeat_task = None
        async def _heartbeat():
            while job_id in self.active_job_ids:
                now = datetime.now(_tz(job)).isoformat(timespec="seconds")
                state.heartbeat_at = now
                if state.current_stage == "STARTING":
                    state.current_stage = "RUNNING"
                    state.current_detail = f"Executing {job.get('transport', 'job')}"
                meta = self.active_job_meta.get(job_id)
                if meta is not None:
                    meta.update({"stage": state.current_stage, "detail": state.current_detail, "heartbeat_at": now})
                await asyncio.sleep(1)
        heartbeat_task = asyncio.create_task(_heartbeat())
        try:
            adapter = ADAPTERS.get(job.get("transport"))
            if not adapter:
                raise RuntimeError(f"Unsupported transport: {job.get('transport')}")
            page = None
            try:
                if job.get("browser_required", True):
                    state.current_stage = "BROWSER"
                    state.current_detail = "Opening dedicated browser page"
                    self.active_job_meta[job_id].update({"stage": "BROWSER", "detail": state.current_detail})
                    page = await self.browser.new_page()
                    state.page_open = True
                    state.current_stage = "EXECUTING"
                    state.current_detail = f"Processing via {job.get('transport', 'job')}"
                result = await asyncio.wait_for(
                    adapter(page, job), timeout=max(5, int(job.get("timeout_seconds", 180)))
                )
            finally:
                state.page_open = False
                if page is not None:
                    await page.close()

            state.current_stage = "FINALIZING"
            state.current_detail = "Validating and finalizing result"
            self.active_job_meta[job_id].update({"stage": "FINALIZING", "detail": state.current_detail})
            result_status = result.get("status", "SUCCESS") if isinstance(result, dict) else "SUCCESS"
            state.state = result_status
            state.download_status = result_status
            state.processing_status = result.get("processing_status", "NOT_RUN") if isinstance(result, dict) else "NOT_RUN"
            state.last_message = result.get("output", result.get("validation", "")) if isinstance(result, dict) else str(result)
            state.last_error_category = result.get("error_category", "") if isinstance(result, dict) else ""
        except asyncio.TimeoutError:
            state.current_stage = "FAILED"
            state.current_detail = "Job timeout"
            state.state = "FAILED"
            state.error_count += 1
            state.last_error_category = "TIMEOUT"
            state.last_message = f"Job exceeded {job.get('timeout_seconds', 180)} seconds"
        except Exception as exc:
            state.current_stage = "FAILED"
            state.current_detail = str(exc)[:240]
            state.state = "FAILED"
            state.error_count += 1
            state.last_error_category = type(exc).__name__
            state.last_message = str(exc)
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            state.last_run = datetime.now(_tz(job)).isoformat(timespec="seconds")
            state.duration_seconds = round(time.perf_counter() - started, 2)
            state.run_count += 1
            if state.state in {"SUCCESS", "COMPLETE"}:
                state.success_count += 1
                state.current_stage = "COMPLETE"
                state.current_detail = "Run completed successfully"
            elif state.state == "PARTIAL":
                state.partial_count += 1
                state.current_stage = "PARTIAL"
                state.current_detail = state.last_message or "Run completed with partial result"
            elif state.state == "FAILED":
                state.failure_count += 1
            state.heartbeat_at = state.last_run
            state.page_open = False
            state.started_at = ""
            state.next_run = _state_next(job)
            self.active_job_ids.discard(job_id)
            self.last_completion[job_id] = datetime.now(_tz(job)).isoformat(timespec="seconds")
            self.active_job_meta.pop(job_id, None)
            try:
                self.states.save()
            except Exception:
                pass

    async def _job_loop(self, job: dict):
        job_id = job["id"]
        while self.running:
            job = self._job(job_id) or job
            normalize_job(job)
            state = self.states.get(job_id)
            # A manual run is allowed even when the job/schedule is disabled.
            # Never let the scheduler loop overwrite its live RUNNING state.
            if job_id in self.active_job_ids:
                await asyncio.sleep(0.5)
                continue
            if not job.get("enabled") or not job.get("schedule", {}).get("enabled", False):
                state.state = "DISABLED"
                state.next_run = ""
                await asyncio.sleep(1)
                continue
            target = next_run(job)
            state.next_run = target.isoformat(timespec="seconds") if target else ""
            if target is None:
                state.state = "WAITING"
                await asyncio.sleep(5)
                continue
            delay = max(0.25, (target - datetime.now(_tz(job))).total_seconds())
            await asyncio.sleep(min(delay, 5.0))
            if delay > 5:
                continue
            if self.running and job.get("enabled") and job.get("schedule", {}).get("enabled", False):
                if in_window(job):
                    await self.run_job(job)
                await asyncio.sleep(0.25)

    async def loop(self):
        self.running = True
        for job in self.jobs:
            normalize_job(job)
            job_id = job.get("id")
            if job_id and job_id not in self.tasks:
                self.tasks[job_id] = asyncio.create_task(self._job_loop(job))
        while self.running:
            # Reconcile newly added/removed jobs without stopping other jobs.
            current = {j.get("id") for j in self.jobs if j.get("id")}
            for job in self.jobs:
                normalize_job(job)
                if job["id"] not in self.tasks:
                    self.tasks[job["id"]] = asyncio.create_task(self._job_loop(job))
            for job_id in list(self.tasks):
                if job_id not in current:
                    self.tasks[job_id].cancel()
                    del self.tasks[job_id]
            await asyncio.sleep(1)

    async def start_async(self):
        self.loop = asyncio.get_running_loop()
        if self.running:
            return
        self.running = True
        # A persisted RUNNING state without a live execution belongs to a prior process.
        for job in self.jobs:
            normalize_job(job)
            state = self.states.get(job.get("id"))
            if state.state == "RUNNING" and job.get("id") not in self.active_job_ids:
                state.state = "DISABLED" if not job.get("enabled") or not job.get("schedule", {}).get("enabled", False) else "WAITING"
                state.next_run = _state_next(job) if state.state == "WAITING" else ""
        try:
            self.states.save()
        except Exception:
            pass
        for job in self.jobs:
            normalize_job(job)
            job_id = job.get("id")
            if job_id and job_id not in self.tasks:
                self.tasks[job_id] = asyncio.create_task(self._job_loop(job))

    async def stop_async(self):
        self.running = False
        for task in list(self.tasks.values()):
            task.cancel()
        self.tasks.clear()
        self.manual_tasks.clear()
        self.active_job_ids.clear()
        self.active_job_meta.clear()

    def stop(self):
        self.running = False
        for task in list(self.tasks.values()):
            task.cancel()
        self.tasks.clear()
        self.manual_tasks.clear()
        self.active_job_ids.clear()
        self.active_job_meta.clear()

    def manual_run(self, job_id: str):
        job = self._job(job_id)
        if not job:
            raise KeyError(job_id)
        if job_id in self.active_job_ids:
            return False
        existing = self.manual_tasks.get(job_id)
        if existing is not None and not existing.done():
            return False
        if self.loop is None or self.loop.is_closed():
            raise RuntimeError("Scheduler event loop is not running")
        future = asyncio.run_coroutine_threadsafe(self.run_job(job, manual=True), self.loop)
        self.manual_tasks[job_id] = future
        def _cleanup(_future):
            current = self.manual_tasks.get(job_id)
            if current is _future:
                self.manual_tasks.pop(job_id, None)
        future.add_done_callback(_cleanup)
        return True

    def runtime_snapshot(self) -> dict:
        return {
            "running": bool(self.running),
            "active_jobs": sorted(self.active_job_ids),
            "active_meta": {k: dict(v) for k, v in self.active_job_meta.items()},
            "last_completion": dict(self.last_completion),
        }


def _state_next(job: dict) -> str:
    n = next_run(job)
    return n.isoformat(timespec="seconds") if n else ""
