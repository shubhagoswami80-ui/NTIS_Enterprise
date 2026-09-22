from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re


@dataclass
class DiscoveryResult:
    url: str
    final_url: str = ""
    title: str = ""
    forms: int = 0
    tables: int = 0
    buttons: int = 0
    selects: int = 0
    downloads: int = 0
    xhr_count: int = 0
    xhr_candidates: list = None
    table_candidates: list = None
    transport_confidence: str = "LOW"
    notes: list = None
    controls: list = None

    def to_dict(self):
        return asdict(self)


async def discover(page, url: str, timeout_ms: int = 45000) -> DiscoveryResult:
    result = DiscoveryResult(
        url=url,
        xhr_candidates=[],
        table_candidates=[],
        notes=[],
        controls=[],
    )
    captured = []

    def redact_post_data(value):
        if not value:
            return ""
        text = str(value)
        text = re.sub(
            r"(?i)(password|passwd|pwd|pass|token|authorization|cookie|secret)=([^&\\s]*)",
            r"\\1=<REDACTED>",
            text,
        )
        return text[:4000]

    def on_response(resp):
        try:
            typ = resp.request.resource_type
            if typ in {"xhr", "fetch"}:
                captured.append({
                    "url": resp.url,
                    "method": resp.request.method,
                    "status": resp.status,
                    "resource_type": typ,
                    "post_data_redacted": redact_post_data(resp.request.post_data),
                    "content_type": resp.headers.get("content-type", ""),
                    "content_length": resp.headers.get("content-length", ""),
                })
        except Exception:
            pass

    page.on("response", on_response)
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    await page.wait_for_timeout(2500)

    result.final_url = page.url
    result.title = await page.title()
    result.forms = await page.locator("form").count()
    result.tables = await page.locator("table").count()
    result.buttons = await page.locator("button").count()
    result.selects = await page.locator("select").count()
    result.downloads = await page.locator("a[download], button[title*='Download'], button:has-text('Download')").count()

    result.controls = await page.locator("input, select, textarea, button").evaluate_all(
        """els => els.map((e, i) => ({
            index: i,
            tag: e.tagName,
            type: e.getAttribute("type") || "",
            name: e.getAttribute("name") || "",
            id: e.id || "",
            value: e.value || "",
            text: (e.innerText || e.textContent || "").trim().slice(0, 300),
            selected: e.tagName === "SELECT"
                ? Array.from(e.options).filter(o => o.selected).map(o => o.text).join("|")
                : "",
            options: e.tagName === "SELECT"
                ? Array.from(e.options).slice(0, 100).map(o => ({value:o.value, text:o.text}))
                : []
        }))"""
    )
    result.xhr_count = len(captured)
    result.xhr_candidates = captured[:100]

    for i in range(min(result.tables, 20)):
        table = page.locator("table").nth(i)
        try:
            headers = await table.locator("th").all_text_contents()
            result.table_candidates.append({
                "index": i,
                "headers": [x.strip() for x in headers if x.strip()],
                "rows": await table.locator("tbody tr").count(),
            })
        except Exception:
            pass

    if result.downloads:
        result.transport_confidence = "HIGH_BROWSER_DOWNLOAD"
    elif result.xhr_count:
        result.transport_confidence = "DISCOVERY_XHR"
    elif result.tables:
        result.transport_confidence = "TABLE_CAPTURE_CANDIDATE"
    else:
        result.transport_confidence = "LOW"

    result.notes.append(
        "Discovery only: no production request replay is activated automatically."
    )
    return result
