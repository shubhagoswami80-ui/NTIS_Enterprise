from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


class XHRReportError(RuntimeError):
    pass


class XHRReportEngine:
    """Generic same-browser-context iCharts XHR response capture engine.

    The page itself creates the authenticated XHR. The engine captures the
    matching response from that page, so dynamic cookies, session IDs,
    expiry values and other request parameters are not hard-coded.
    """

    def __init__(self, logger=None):
        self.logger = logger or (lambda message: None)

    def log(self, message):
        self.logger(message)

    @staticmethod
    def _safe_filename(value):
        value = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(value)).strip()
        return value or "xhr_report"

    @staticmethod
    def _response_rows(response_text):
        try:
            data = json.loads(response_text)
        except Exception as exc:
            raise XHRReportError(f"XHR response is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise XHRReportError("XHR response root is not an object")
        rows = data.get("aaData")
        if not isinstance(rows, list):
            raise XHRReportError("XHR response does not contain aaData rows")
        return data, rows

    @staticmethod
    def _extract_headers(page):
        try:
            headers = page.locator("table thead th").all_inner_texts()
            headers = [" ".join(str(x).split()) for x in headers]
            headers = [x for x in headers if x]
            if headers:
                return headers
        except Exception:
            pass
        return []

    @staticmethod
    def _unique_headers(headers, width):
        result = []
        seen = {}
        for index in range(width):
            raw = headers[index] if index < len(headers) else f"Column_{index + 1:02d}"
            name = str(raw).strip() or f"Column_{index + 1:02d}"
            count = seen.get(name, 0) + 1
            seen[name] = count
            if count > 1:
                name = f"{name}_{count}"
            result.append(name)
        return result

    def _write_cycle(self, destination, job, data, rows, headers):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        cycle_dir = destination / "XHR"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = self._safe_filename(job.get("output_stem", job.get("name", "xhr_report")))

        payload = {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "report_id": job.get("id", ""),
            "report_name": job.get("name", ""),
            "page_url": job.get("page_url", ""),
            "endpoint": job.get("endpoint", ""),
            "http_status": data.get("_http_status"),
            "total_records": data.get("iTotalRecords"),
            "total_display_records": data.get("iTotalDisplayRecords"),
            "columns": headers,
            "aaData": rows,
        }
        payload.pop("_http_status", None)

        raw_path = cycle_dir / f"{stem}_{stamp}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_path = cycle_dir / f"{stem}_Latest.json"
        latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            import pandas as pd
            frame = pd.DataFrame(rows, columns=self._unique_headers(headers, max((len(r) for r in rows), default=0)))
            xlsx_path = cycle_dir / f"{stem}_{stamp}.xlsx"
            latest_xlsx = cycle_dir / f"{stem}_Latest.xlsx"
            frame.to_excel(xlsx_path, index=False)
            frame.to_excel(latest_xlsx, index=False)
            return raw_path, latest_path, xlsx_path, latest_xlsx
        except Exception as exc:
            raise XHRReportError(f"Excel write failed: {exc}") from exc

    def run(self, context, production_page, job):
        if context is None or production_page is None or production_page.is_closed():
            raise XHRReportError("Existing production browser/page is not alive")

        target_url = str(job.get("page_url", "")).strip()
        endpoint = str(job.get("endpoint", "")).strip()
        destination = str(job.get("destination", "")).strip()
        if not target_url or not endpoint or not destination:
            raise XHRReportError("page_url, endpoint and destination are required")

        pece_page = context.new_page()
        captured = {}

        def on_response(response):
            try:
                if response.request.resource_type != "xhr":
                    return
                if response.url.rstrip("/") != endpoint.rstrip("/"):
                    return
                captured["response"] = response
            except Exception:
                pass

        pece_page.on("response", on_response)
        try:
            self.log(f"{job.get('name', 'XHR report')}: opening page in existing browser context")
            pece_page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            pece_page.wait_for_timeout(int(float(job.get("page_wait_seconds", 3)) * 1000))

            if "login" in pece_page.url.lower() or "signin" in pece_page.url.lower():
                raise XHRReportError("iCharts login/session is required")

            deadline = datetime.now().timestamp() + float(job.get("capture_wait_seconds", 15))
            while "response" not in captured and datetime.now().timestamp() < deadline:
                pece_page.wait_for_timeout(250)

            if "response" not in captured:
                raise XHRReportError(f"Target XHR response not observed: {endpoint}")

            response = captured["response"]
            if not response.ok:
                raise XHRReportError(f"XHR HTTP {response.status}")
            body = response.text()
            data, rows = self._response_rows(body)
            if not rows:
                raise XHRReportError("XHR returned zero rows")

            configured_columns = job.get("columns") or []
            dom_columns = self._extract_headers(pece_page)
            headers = configured_columns or dom_columns
            width = max((len(row) for row in rows), default=0)
            headers = self._unique_headers(headers, width)
            data["_http_status"] = response.status

            paths = self._write_cycle(destination, job, data, rows, headers)
            self.log(f"{job.get('name', 'XHR report')}: {len(rows)} rows saved -> {paths[2]}")
            return paths[0], paths[3], len(rows)
        finally:
            try:
                pece_page.close()
            except Exception:
                pass
