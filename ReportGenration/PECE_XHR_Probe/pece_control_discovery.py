from pathlib import Path
from datetime import datetime
import json
import re

TARGET_URL = "https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php"
ENDPOINT_RE = re.compile(r"getDataForTotalPECEOIDiff", re.I)

def _sanitize_post_data(post_data):
    """Return POST data with session/credential-like values redacted."""
    if not post_data:
        return None
    from urllib.parse import parse_qsl, urlencode
    try:
        pairs = parse_qsl(post_data, keep_blank_values=True)
    except Exception:
        return "[REDACTED_UNPARSEABLE_POST_DATA]"
    sensitive = {
        "sessionid", "phpsessid", "token", "password", "passwd",
        "userpassword", "username", "user_name", "cf_clearance"
    }
    out = []
    for key, value in pairs:
        if key.strip().lower() in sensitive:
            value = "[REDACTED]"
        out.append((key, value))
    return urlencode(out)

def discover_pece_controls(context, target_url=TARGET_URL, current_symbol=None,
                           output_root=None, wait_seconds=12):
    if context is None:
        raise RuntimeError("Browser context is not available")
    pages_before = list(context.pages)
    production_page = pages_before[0] if pages_before else None
    if production_page is None or production_page.is_closed():
        raise RuntimeError("Existing authenticated page is not available")

    root = Path(output_root or "pece_xhr_probe")
    capture = root / f"symbol_discovery_{datetime.now():%Y%m%d_%H%M%S}"
    capture.mkdir(parents=True, exist_ok=True)

    page = context.new_page()
    responses, failures, errors = [], [], []

    def on_response(response):
        try:
            if (ENDPOINT_RE.search(response.url)
                    and response.request.resource_type in ("xhr", "fetch")):
                item = {
                    "url": response.url,
                    "status": response.status,
                    "resource_type": response.request.resource_type,
                    "content_type": response.headers.get("content-type", ""),
                    "post_data": _sanitize_post_data(response.request.post_data),
                }
                try:
                    body = response.body()
                    fn = f"response_{len(responses)+1:04d}.bin"
                    (capture / fn).write_bytes(body)
                    item["body_file"] = fn
                    item["body_bytes"] = len(body)
                except Exception as exc:
                    item["body_error"] = str(exc)
                responses.append(item)
        except Exception as exc:
            errors.append(str(exc))

    page.on("response", on_response)
    page.on("requestfailed", lambda r: failures.append({
        "url": r.url, "method": r.method, "failure": r.failure
    }))
    page.on("pageerror", lambda e: errors.append(str(e)))

    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_seconds * 1000)

        def inspect(selector, limit):
            result = []
            loc = page.locator(selector)
            for i in range(min(loc.count(), limit)):
                el = loc.nth(i)
                try:
                    result.append(el.evaluate("""
                        el => ({
                            tag: el.tagName,
                            id: el.id || "",
                            name: el.name || "",
                            value: el.value || "",
                            type: el.type || "",
                            className: el.className || "",
                            aria: el.getAttribute("aria-label") || "",
                            title: el.getAttribute("title") || "",
                            options: el.tagName === "SELECT"
                              ? Array.from(el.options || []).map(o => ({
                                  text: (o.textContent || "").trim(),
                                  value: o.value || "",
                                  selected: !!o.selected
                                })).slice(0,500)
                              : []
                        })
                    """))
                except Exception:
                    pass
            return result

        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_url": target_url,
            "current_symbol": current_symbol,
            "production_page_url_before": production_page.url,
            "selects": inspect("select", 100),
            "inputs": inspect("input:not([type='hidden'])", 300),
            "buttons": inspect("button, a, [role='button']", 300),
            "responses": responses,
            "request_failures": failures,
            "errors": errors,
        }
        (capture / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return manifest
    finally:
        try:
            if not page.is_closed():
                page.close()
        finally:
            if (capture / "manifest.json").exists():
                try:
                    data = json.loads(
                        (capture / "manifest.json").read_text(encoding="utf-8")
                    )
                    data["temporary_page_closed"] = True
                    data["production_page_url_after"] = production_page.url
                    data["production_page_alive_after"] = not production_page.is_closed()
                    data["pages_after_close"] = len(context.pages)
                    (capture / "manifest.json").write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                except Exception:
                    pass
