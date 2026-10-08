from __future__ import annotations

import re
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .pathing import final_report_path
from .validation import validate_output
from .optionchain_end_to_end_collector_v3 import run_optionchain_end_to_end_collector_v3
from .optionchain_daily_universe import get_or_create_daily_universe
from .specialized_transports import support_resistance, pece_xhr_batch


def _dynamic_destination(job: dict) -> Path:
    raw = str(job.get("output_root") or job.get("destination") or "").strip()
    if not raw:
        raise RuntimeError(
            f"{job.get('name', job.get('id', 'job'))}: destination folder is empty"
        )
    root = Path(raw)
    now = datetime.now()
    month_folder = now.strftime("%B") + now.strftime("%y")
    day_folder = now.strftime("%Y-%m-%d")
    destination = root / month_folder / day_folder
    destination.mkdir(parents=True, exist_ok=True)
    return destination



async def browser_download(page, job: dict) -> dict:
    started = time.perf_counter()
    name = job.get("name", job.get("id", "job"))
    timeout_ms = int(float(job.get("timeout_seconds", 90)) * 1000)
    wait_ms = int(float(job.get("wait_seconds", 2)) * 1000)

    await page.goto(job["url"], wait_until="domcontentloaded", timeout=timeout_ms)
    await page.wait_for_timeout(1000)
    if "login" in page.url.lower() or "signin" in page.url.lower():
        raise RuntimeError(f"{name}: login required")

    action = job.get("action", "refresh")
    if action in ("refresh", "refresh_submit"):
        await page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(wait_ms)

    if action in ("submit", "refresh_submit"):
        selector = job.get("submit_selector") or 'button:has-text("SUBMIT")'
        button = page.locator(selector).first
        if await button.count() == 0:
            raise RuntimeError(f"{name}: Submit button not found")
        await button.click(force=True)
        await page.wait_for_timeout(wait_ms)

    destination = _dynamic_destination(job)
    selector = job.get("download_selector") or 'button[title="Download Excel"]'
    button = page.locator(selector).first

    fallbacks = [
        'button[title*="Excel" i]', 'a[title*="Excel" i]', '[role="button"][title*="Excel" i]',
        'button[aria-label*="Excel" i]', 'a[aria-label*="Excel" i]', '[role="button"][aria-label*="Excel" i]',
        'button[title*="Download" i]', 'a[title*="Download" i]', '[role="button"][title*="Download" i]',
        'button[aria-label*="Download" i]', 'a[aria-label*="Download" i]', '[role="button"][aria-label*="Download" i]',
        'button[title*="Export" i]', 'a[title*="Export" i]', '[role="button"][title*="Export" i]',
        'button[aria-label*="Export" i]', 'a[aria-label*="Export" i]', '[role="button"][aria-label*="Export" i]',
    ]
    if await button.count() == 0:
        for s in fallbacks:
            loc = page.locator(s).first
            if await loc.count():
                button = loc
                break
    if await button.count() == 0:
        controls = page.locator('button, a, [role="button"]')
        for i in range(await controls.count()):
            c = controls.nth(i)
            try:
                d = await c.evaluate("""el => ({text:(el.innerText||'').trim(),title:el.getAttribute('title')||'',aria:el.getAttribute('aria-label')||'',id:el.id||'',cls:typeof el.className==='string'?el.className:'',html:(el.outerHTML||'').slice(0,1500)})""")
            except Exception:
                continue
            combined = " ".join(str(d.get(k, "")) for k in ("text","title","aria","id","cls","html")).casefold()
            if any(x in combined for x in ("excel", "download", "export", ".xlsx", ".xls")):
                button = c
                break
    if await button.count() == 0:
        raise RuntimeError(f"{name}: Download button not found after report action")

    async with page.expect_download(timeout=30000) as event:
        await button.click(force=True)
    download = await event.value
    filename = download.suggested_filename or f"{job['id']}_{datetime.now():%Y%m%d_%H%M%S}.xls"
    p = Path(filename)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = destination / f"{p.stem}_{stamp}{p.suffix}"
    counter = 1
    while output.exists():
        output = destination / f"{p.stem}_{stamp}_{counter:02d}{p.suffix}"
        counter += 1
    await download.save_as(str(output))
    ok, validation = validate_output(output, job.get("required_sheets", []))
    return {"status":"SUCCESS" if ok else "PARTIAL", "output":str(output), "validation":validation, "download_status":"COMPLETE", "processing_status":"COMPLETE", "duration_seconds":round(time.perf_counter()-started,2)}


async def optionchain_end_to_end(page, job: dict) -> dict:
    started = time.perf_counter()
    output_root = job.get("output_root") or job.get("destination")
    if not output_root:
        raise RuntimeError("Option Chain output_root is not configured")
    await page.goto(job.get("url", "https://www.icharts.in/opt/OptionChain.php"), wait_until="domcontentloaded", timeout=int(job.get("timeout_seconds",900)*1000))
    await page.wait_for_timeout(int(float(job.get("wait_seconds",1))*1000))
    today = datetime.now().date()
    if job.get("use_daily_universe", True):
        symbols, universe_meta, universe_path = await get_or_create_daily_universe(page, output_root, today, force_refresh=False)
    else:
        symbols = [str(x).strip().upper() for x in job.get("symbols",[]) if str(x).strip()]
        universe_meta={"source_state":"JOB_CONFIG","symbol_count":len(symbols)}; universe_path=""
    if not symbols: raise RuntimeError("Option Chain daily universe returned zero symbols")
    result = await run_optionchain_end_to_end_collector_v3(context=page.context, symbols=symbols, output_root=output_root, replay_concurrency=int(job.get("replay_concurrency",job.get("concurrency",5))), capture_concurrency=int(job.get("capture_concurrency",5)), timeout_seconds=int(job.get("request_timeout_seconds",30)), max_retries=int(job.get("retry_count",2)), backoff_initial_ms=int(job.get("backoff_initial_ms",1500)), backoff_max_ms=int(job.get("backoff_max_ms",15000)), request_gap_ms=int(job.get("request_gap_ms",250)), jitter_ms=int(job.get("jitter_ms",500)), replay_429_cooldown_ms=int(job.get("replay_429_cooldown_ms",5000)))
    result.update(universe_source_state=universe_meta.get("source_state",""), universe_symbol_count=len(symbols), universe_path=str(universe_path), processing_status=result.get("overall_status","PARTIAL"), output=result.get("output_file",""), validation=f"{result.get('passed',0)} collected; {result.get('no_data',0)} no-data; {result.get('failed',0)} failed; {result.get('overall_status','PARTIAL')}", duration_seconds=round(time.perf_counter()-started,2), status="SUCCESS" if result.get("overall_status")=="COMPLETE" else "PARTIAL", error_category="")
    return result


async def discovery_pending(page, job):
    raise RuntimeError("Production acquisition is blocked until the site's actual request mechanism is validated.")


ADAPTERS = {
    "browser_download": browser_download,
    "support_resistance": support_resistance,
    "icharts_xhr_batch": pece_xhr_batch,
    "pece_xhr_batch": pece_xhr_batch,
    "discovery_pending": discovery_pending,
    "optionchain_end_to_end": optionchain_end_to_end,
}
