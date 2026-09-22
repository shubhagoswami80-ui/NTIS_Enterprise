from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time

from .consolidation import write_cycle_workbook, write_manifest
from .pathing import final_report_path, trace_dir
from .validation import validate_output


async def browser_download(page, job: dict) -> dict:
    started = time.perf_counter()
    url = job["url"]

    await page.goto(url, wait_until="domcontentloaded", timeout=int(job["timeout_seconds"] * 1000))
    await page.wait_for_timeout(int(float(job.get("wait_seconds", 2)) * 1000))

    action = job.get("action", "none")
    if action == "refresh":
        await page.reload(wait_until="domcontentloaded")
    elif action == "submit":
        if job.get("submit_selector"):
            await page.locator(job["submit_selector"]).click()
    elif action == "radio_submit":
        selection = job.get("selection", "")
        if selection:
            loc = page.locator(f"input[type='radio'][value='{selection}']")
            if await loc.count():
                await loc.first.check()
        if job.get("submit_selector"):
            await page.locator(job["submit_selector"]).click()

    selector = job.get("download_selector")
    if not selector:
        raise RuntimeError("download_selector is not configured")

    async with page.expect_download(timeout=int(job["timeout_seconds"] * 1000)) as info:
        await page.locator(selector).click()

    download = await info.value
    output = final_report_path(job)
    await download.save_as(str(output))

    ok, validation = validate_output(output, job.get("required_sheets", []))
    return {
        "status": "SUCCESS" if ok else "PARTIAL",
        "output": str(output),
        "validation": validation,
        "duration_seconds": round(time.perf_counter() - started, 2),
    }


async def discovery_pending(page, job: dict) -> dict:
    raise RuntimeError(
        "Option Chain production acquisition is intentionally blocked until "
        "URL discovery validates the site's actual symbol/request mechanism."
    )


ADAPTERS = {
    "browser_download": browser_download,
    "discovery_pending": discovery_pending,
}
