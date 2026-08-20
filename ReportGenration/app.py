import json
import queue
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "reports.json"
PROFILE = ROOT / "browser_profile"
LOGS = ROOT / "logs"

PROFILE.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)


def norm_time(value):
    return datetime.strptime(
        str(value).strip().replace(".", ":"),
        "%H:%M",
    ).strftime("%H:%M")


def load():
    if CFG.exists():
        try:
            return json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "start_time": "09:25",
        "stop_time": "18:30",
        "jobs": [],
    }


def save(config):
    CFG.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )


class Manager:
    def __init__(self):
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.s = {
            "browser": "Not started",
            "running": False,
            "message": "Ready",
            "last_download": "",
            "next_download": "",
        }
        threading.Thread(
            target=self.worker,
            daemon=True,
        ).start()

    def set(self, **kwargs):
        with self.lock:
            self.s.update(kwargs)

    def snap(self):
        with self.lock:
            return dict(self.s)

    def cmd(self, name, data=None):
        self.q.put((name, data or {}))

    def log(self, message):
        logfile = LOGS / f"{datetime.now():%Y-%m-%d}.log"
        with logfile.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}\n"
            )
        self.set(message=message)

    def alive(self, context, page):
        try:
            return (
                context is not None
                and page is not None
                and not page.is_closed()
                and len(context.pages) > 0
            )
        except Exception:
            return False

    def open_browser(self, playwright):
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            accept_downloads=True,
        )
        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )
        self.set(browser="Open")
        return context, page

    def ensure_browser(self, playwright, context, page):
        if self.alive(context, page):
            return context, page

        try:
            if context:
                context.close()
        except Exception:
            pass

        self.log("Opening/reopening Chromium session...")
        return self.open_browser(playwright)

    def worker(self):
        with sync_playwright() as playwright:
            context = None
            page = None
            running = False
            start_time = "09:25"
            stop_time = "18:30"
            jobs = []
            due = {}

            while True:
                try:
                    while True:
                        try:
                            command, data = self.q.get_nowait()
                        except queue.Empty:
                            break

                        if command == "open":
                            context, page = self.ensure_browser(
                                playwright,
                                context,
                                page,
                            )
                            self.set(
                                browser="Open",
                                message="Browser session opened/reopened.",
                            )

                        elif command == "start":
                            start_time = norm_time(data["start"])
                            stop_time = norm_time(data["stop"])
                            jobs = data["jobs"]

                            context, page = self.ensure_browser(
                                playwright,
                                context,
                                page,
                            )

                            now = datetime.now()
                            due = {
                                job["id"]: now
                                for job in jobs
                                if job.get("enabled", True)
                            }

                            running = True
                            self.set(
                                running=True,
                                next_download="",
                                message=(
                                    f"Daily run started: "
                                    f"{start_time} to {stop_time}"
                                ),
                            )
                            self.log(
                                f"Daily run started: "
                                f"{start_time} to {stop_time}"
                            )

                        elif command == "stop":
                            running = False
                            self.set(
                                running=False,
                                next_download="",
                                message="Stopped",
                            )
                            self.log("Daily run stopped manually.")

                        elif command == "shutdown":
                            try:
                                if context:
                                    context.close()
                            except Exception:
                                pass
                            return

                    if running:
                        context, page = self.ensure_browser(
                            playwright,
                            context,
                            page,
                        )

                        now = datetime.now()
                        start_clock = datetime.strptime(
                            start_time,
                            "%H:%M",
                        ).time()
                        stop_clock = datetime.strptime(
                            stop_time,
                            "%H:%M",
                        ).time()

                        if now.time() >= stop_clock:
                            running = False
                            self.set(
                                running=False,
                                next_download="",
                                message="Automatic stop time reached.",
                            )
                            self.log(
                                "Automatic stop time reached."
                            )

                        elif now.time() < start_clock:
                            self.set(
                                message=(
                                    f"Waiting for start time "
                                    f"{start_time}"
                                )
                            )

                        else:
                            for job in jobs:
                                if not job.get("enabled", True):
                                    continue

                                if now >= due.get(
                                    job["id"],
                                    now,
                                ):
                                    self.download(page, job)

                                    interval = max(
                                        1,
                                        int(
                                            job.get(
                                                "interval_minutes",
                                                15,
                                            )
                                        ),
                                    )

                                    due[job["id"]] = (
                                        datetime.now()
                                        + timedelta(
                                            minutes=interval
                                        )
                                    )

                            future = [
                                value
                                for value in due.values()
                                if value > now
                            ]

                            self.set(
                                next_download=(
                                    min(future).strftime("%H:%M:%S")
                                    if future
                                    else ""
                                )
                            )

                    time.sleep(0.5)

                except Exception as error:
                    self.log(
                        f"Automation error: {error}"
                    )
                    time.sleep(2)

    def select_option(self, page, job):
        value = str(
            job.get("selection", "")
        ).strip()

        selector = str(
            job.get("selection_selector", "")
        ).strip()

        if not value and not selector:
            return True

        def norm(text):
            return " ".join(
                str(text or "").split()
            ).strip().casefold()

        wanted = norm(value)

        try:
            # 1. Explicit selector supplied by the user.
            if selector:
                locator = page.locator(selector).first

                if locator.count() == 0:
                    self.log(
                        f"{job['name']}: selection selector "
                        f"not found: {selector}"
                    )
                    return False

                try:
                    locator.check(force=True)
                except Exception:
                    locator.click(force=True)

                page.wait_for_timeout(300)
                return True

            # 2. Prefer actual radio inputs and inspect their
            # value/id/name plus associated label/container text.
            radios = page.locator('input[type="radio"]')

            for index in range(radios.count()):
                radio = radios.nth(index)

                try:
                    details = radio.evaluate(
                        """
                        el => {
                            const label = el.id
                                ? document.querySelector(
                                    `label[for="${CSS.escape(el.id)}"]`
                                  )
                                : null;
                            const parentLabel = el.closest("label");
                            const container = el.closest(
                                "label, td, th, div, span, li"
                            );

                            return {
                                value: el.value || "",
                                id: el.id || "",
                                name: el.name || "",
                                aria: el.getAttribute("aria-label") || "",
                                title: el.getAttribute("title") || "",
                                label: label ? label.innerText : "",
                                parentLabel: parentLabel
                                    ? parentLabel.innerText
                                    : "",
                                container: container
                                    ? container.innerText
                                    : ""
                            };
                        }
                        """
                    )
                except Exception:
                    continue

                candidates = [
                    details.get("value"),
                    details.get("id"),
                    details.get("name"),
                    details.get("aria"),
                    details.get("title"),
                    details.get("label"),
                    details.get("parentLabel"),
                    details.get("container"),
                ]

                if any(
                    wanted == norm(candidate)
                    for candidate in candidates
                ):
                    try:
                        radio.check(force=True)
                    except Exception:
                        radio.click(force=True)

                    page.wait_for_timeout(300)
                    self.log(
                        f"{job['name']}: selected radio option "
                        f"'{value}'."
                    )
                    return True

            # 3. Fallback to an exact matching label.
            labels = page.locator("label")

            for index in range(labels.count()):
                label = labels.nth(index)

                try:
                    text = label.inner_text().strip()
                except Exception:
                    continue

                if norm(text) != wanted:
                    continue

                try:
                    label.click(force=True)
                    page.wait_for_timeout(300)
                    self.log(
                        f"{job['name']}: selected option "
                        f"'{value}' via label."
                    )
                    return True
                except Exception:
                    continue

            # 4. Final visible-text fallback for unusual page markup.
            locator = page.get_by_text(
                value,
                exact=True,
            ).first

            if locator.count() > 0:
                try:
                    locator.click(force=True)
                    page.wait_for_timeout(300)
                    self.log(
                        f"{job['name']}: selected option "
                        f"'{value}' via text."
                    )
                    return True
                except Exception:
                    pass

            self.log(
                f"{job['name']}: selection not found: "
                f"'{value}'."
            )
            return False

        except Exception as error:
            self.log(
                f"{job['name']}: selection error: {error}"
            )
            return False

    @staticmethod
    def transform_filename(filename, rule):
        """
        Current supported custom rule:

        replace_leading_support_with_resistance

        Website filename:
            Support_Resistance_25AUG26_Scan_14_8_2026.xlsx

        Result:
            Resistance_25AUG26_Scan_14_8_2026.xlsx

        The rule removes the literal leading 'Support_'
        from the website filename and keeps the remaining
        'Resistance_' portion untouched.
        """
        if rule == "replace_leading_support_with_resistance":
            # Normalize both possible website filename forms.
            # Never prepend a second "Resistance_".
            if filename.startswith("Support_Resistance_"):
                return (
                    "Resistance_"
                    + filename[len("Support_Resistance_"):]
                )

            # The site may already return a Resistance-prefixed name,
            # and a previous run/configuration may have produced a
            # duplicated prefix. Normalize any repeated prefix.
            while filename.startswith("Resistance_Resistance_"):
                filename = filename[len("Resistance_"):]

            if filename.startswith("Resistance_"):
                return filename

        return filename

    def download(self, page, job):
        name = job["name"]
        destination_text = str(
            job.get("destination", "")
        ).strip()

        if not destination_text:
            self.log(
                f"{name}: destination folder is empty."
            )
            return

        try:
            # A transient Chromium/network suspension can invalidate the
            # current Page object. Retry navigation once only, and always
            # reacquire a live page after browser recovery.
            navigation_error = None

            for navigation_attempt in range(2):
                try:
                    if (
                        self.context is None
                        or self.browser is None
                        or len(self.context.pages) == 0
                    ):
                        self.open_browser()

                    page = self.context.pages[-1]

                    page.goto(
                        job["url"],
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    navigation_error = None
                    break

                except Exception as error:
                    navigation_error = error

                    if navigation_attempt == 0:
                        self.log(
                            f"{name}: navigation failed; "
                            f"reopening Chromium and retrying: {error}"
                        )
                        try:
                            self.open_browser()
                        except Exception as recovery_error:
                            navigation_error = recovery_error
                            break

            if navigation_error is not None:
                self.log(
                    f"{name}: download failed during navigation: "
                    f"{navigation_error}"
                )
                return

            page.wait_for_timeout(1000)

            if (
                "login" in page.url.lower()
                or "signin" in page.url.lower()
            ):
                self.log(
                    f"{name}: login required."
                )
                return

            action = job.get(
                "action",
                "refresh",
            )

            wait_ms = int(
                float(
                    job.get(
                        "wait_seconds",
                        2,
                    )
                )
                * 1000
            )

            if action in (
                "refresh",
                "refresh_submit",
            ):
                page.reload(
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_timeout(
                    wait_ms
                )

            if action in (
                "radio_submit",
                "radio",
            ):
                if not self.select_option(
                    page,
                    job,
                ):
                    return

            if action in (
                "submit",
                "refresh_submit",
                "radio_submit",
            ):
                submit_selector = (
                    job.get("submit_selector")
                    or 'button:has-text("SUBMIT")'
                )

                button = page.locator(
                    submit_selector
                ).first

                if button.count() == 0:
                    self.log(
                        f"{name}: Submit button not found."
                    )
                    return

                button.click()
                page.wait_for_timeout(
                    wait_ms
                )

            destination = Path(
                destination_text
            )
            destination.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Keep the configured selector as the first choice.
            # Some iCharts pages use an icon-only export control
            # whose title/HTML differs from the configured selector.
            download_selector = (
                job.get("download_selector")
                or 'button[title="Download Excel"]'
            )

            button = page.locator(
                download_selector
            ).first

            # Fallback selectors for icon-only Excel/download controls.
            # These are intentionally restricted to attributes normally
            # associated with the Excel/export control.
            if button.count() == 0:
                fallback_selectors = [
                    'button[title*="Excel" i]',
                    'a[title*="Excel" i]',
                    '[role="button"][title*="Excel" i]',
                    'button[aria-label*="Excel" i]',
                    'a[aria-label*="Excel" i]',
                    '[role="button"][aria-label*="Excel" i]',
                    'button[title*="Download" i]',
                    'a[title*="Download" i]',
                    '[role="button"][title*="Download" i]',
                    'button[aria-label*="Download" i]',
                    'a[aria-label*="Download" i]',
                    '[role="button"][aria-label*="Download" i]',
                    'button[title*="Export" i]',
                    'a[title*="Export" i]',
                    '[role="button"][title*="Export" i]',
                    'button[aria-label*="Export" i]',
                    'a[aria-label*="Export" i]',
                    '[role="button"][aria-label*="Export" i]',
                ]

                for candidate in fallback_selectors:
                    locator = page.locator(candidate).first
                    if locator.count() > 0:
                        button = locator
                        self.log(
                            f"{name}: using fallback download "
                            f"selector: {candidate}"
                        )
                        break

            # Last-resort inspection of visible export/download
            # controls. This handles pages where the icon's useful
            # text is stored on a nested element rather than the
            # button itself.
            if button.count() == 0:
                candidates = page.locator(
                    'button, a, [role="button"]'
                )

                for index in range(candidates.count()):
                    candidate = candidates.nth(index)

                    try:
                        details = candidate.evaluate(
                            """
                            el => ({
                                text: (el.innerText || "").trim(),
                                title: el.getAttribute("title") || "",
                                aria: el.getAttribute("aria-label") || "",
                                id: el.id || "",
                                cls: el.className || "",
                                html: (el.outerHTML || "").slice(0, 1500)
                            })
                            """
                        )
                    except Exception:
                        continue

                    combined = " ".join(
                        str(details.get(key, ""))
                        for key in (
                            "text",
                            "title",
                            "aria",
                            "id",
                            "cls",
                            "html",
                        )
                    ).casefold()

                    if (
                        "excel" in combined
                        or "download" in combined
                        or "export" in combined
                        or ".xlsx" in combined
                        or ".xls" in combined
                    ):
                        button = candidate
                        self.log(
                            f"{name}: found fallback export/download "
                            f"control."
                        )
                        break

            if button.count() == 0:
                self.log(
                    f"{name}: Download button not found. "
                    f"Configured selector: {download_selector}"
                )
                return

            with page.expect_download(
                timeout=30000
            ) as event:
                button.click(force=True)

            download = event.value

            filename = (
                download.suggested_filename
                or (
                    f"{job['id']}_"
                    f"{datetime.now():%Y%m%d_%H%M%S}.xls"
                )
            )

            # New custom filename rule.
            # Support keeps the website filename.
            # Resistance removes the leading "Support_"
            # and changes it to "Resistance_".
            filename = self.transform_filename(
                filename,
                job.get("filename_rule", ""),
            )

            # Keep backward compatibility with the existing
            # suffix field if a future job uses it.
            suffix = str(
                job.get("filename_suffix", "")
            ).strip()

            if suffix:
                path = Path(filename)
                filename = (
                    f"{path.stem}_{suffix}"
                    f"{path.suffix}"
                )

            output = destination / filename

            if output.exists():
                path = output
                output = destination / (
                    f"{path.stem}_"
                    f"{datetime.now():%H%M%S}"
                    f"{path.suffix}"
                )

            download.save_as(
                str(output)
            )

            self.set(
                last_download=(
                    f"{name} | {output}"
                ),
                message=(
                    f"{name}: download completed."
                ),
            )

            self.log(
                f"{name}: saved -> {output}"
            )

        except Exception as error:
            self.log(
                f"{name}: download failed: {error}"
            )


st.set_page_config(
    page_title="Online Report Downloader",
    layout="wide",
)

@st.cache_resource
def get_manager():
    return Manager()


manager = get_manager()
config = load()
status = manager.snap()

if "jobs" not in st.session_state:
    st.session_state.jobs = config.get(
        "jobs",
        [],
    )

if "start" not in st.session_state:
    st.session_state.start = config.get(
        "start_time",
        "09:25",
    )

if "stop" not in st.session_state:
    st.session_state.stop = config.get(
        "stop_time",
        "18:30",
    )


st.title("Online Report Downloader")
st.caption(
    "Multiple report jobs • persistent login • "
    "configurable refresh/submit/radio actions"
)

col1, col2 = st.columns(2)

with col1:
    start_time = st.text_input(
        "Start time",
        st.session_state.start,
        disabled=status["running"],
    )

with col2:
    stop_time = st.text_input(
        "Stop time",
        st.session_state.stop,
        disabled=status["running"],
    )

st.subheader("Report Jobs")

actions = [
    "refresh",
    "submit",
    "refresh_submit",
    "radio_submit",
    "radio",
    "none",
]

labels = {
    "refresh": "Refresh → Download",
    "submit": "Submit → Download",
    "refresh_submit": "Refresh → Submit → Download",
    "radio_submit": "Select option → Submit → Download",
    "radio": "Select option → Download",
    "none": "None → Download",
}

for index, job in enumerate(
    st.session_state.jobs
):
    with st.expander(
        f"{index + 1}. {job.get('name', 'New Report')}",
        expanded=(index == 0),
    ):
        left, right = st.columns(2)

        with left:
            job["name"] = st.text_input(
                "Report name",
                job.get("name", ""),
                key=f"name_{index}",
                disabled=status["running"],
            )

            job["url"] = st.text_input(
                "URL",
                job.get("url", ""),
                key=f"url_{index}",
                disabled=status["running"],
            )

            current_action = job.get(
                "action",
                "refresh",
            )

            if current_action not in actions:
                current_action = "refresh"

            job["action"] = st.selectbox(
                "Before download",
                actions,
                index=actions.index(
                    current_action
                ),
                format_func=lambda value: labels[
                    value
                ],
                key=f"action_{index}",
                disabled=status["running"],
            )

            if job["action"] in (
                "radio_submit",
                "radio",
            ):
                job["selection"] = st.text_input(
                    "Option text",
                    job.get(
                        "selection",
                        "",
                    ),
                    key=f"selection_{index}",
                    disabled=status["running"],
                )

                job["selection_selector"] = st.text_input(
                    "Option selector (optional)",
                    job.get(
                        "selection_selector",
                        "",
                    ),
                    key=f"selection_selector_{index}",
                    disabled=status["running"],
                )

        with right:
            job["interval_minutes"] = st.number_input(
                "Interval (minutes)",
                min_value=1,
                max_value=240,
                value=int(
                    job.get(
                        "interval_minutes",
                        15,
                    )
                ),
                step=1,
                key=f"interval_{index}",
                disabled=status["running"],
            )

            job["destination"] = st.text_input(
                "Destination folder",
                job.get(
                    "destination",
                    "",
                ),
                key=f"destination_{index}",
                disabled=status["running"],
            )

            job["wait_seconds"] = st.number_input(
                "Wait after Refresh / Submit (seconds)",
                min_value=0.5,
                max_value=60.0,
                value=float(
                    job.get(
                        "wait_seconds",
                        2,
                    )
                ),
                step=0.5,
                key=f"wait_{index}",
                disabled=status["running"],
            )

            job["submit_selector"] = st.text_input(
                "Submit selector",
                job.get(
                    "submit_selector",
                    'button:has-text("SUBMIT")',
                ),
                key=f"submit_{index}",
                disabled=status["running"],
            )

            job["download_selector"] = st.text_input(
                "Download selector",
                job.get(
                    "download_selector",
                    'button[title="Download Excel"]',
                ),
                key=f"download_{index}",
                disabled=status["running"],
            )

            # The old suffix field is retained so existing
            # configurations are not broken.
            job["filename_suffix"] = st.text_input(
                "Filename suffix (optional)",
                job.get(
                    "filename_suffix",
                    "",
                ),
                key=f"suffix_{index}",
                disabled=status["running"],
            )

            job["filename_rule"] = st.selectbox(
                "Filename rule",
                [
                    "",
                    "replace_leading_support_with_resistance",
                ],
                index=(
                    1
                    if job.get("filename_rule")
                    == "replace_leading_support_with_resistance"
                    else 0
                ),
                format_func=lambda value: {
                    "": "Keep website filename",
                    "replace_leading_support_with_resistance":
                        "Resistance: Support_ → Resistance_",
                }[value],
                key=f"filename_rule_{index}",
                disabled=status["running"],
            )

            job["enabled"] = st.checkbox(
                "Enabled",
                value=bool(
                    job.get(
                        "enabled",
                        True,
                    )
                ),
                key=f"enabled_{index}",
                disabled=status["running"],
            )

        if not status["running"]:
            if st.button(
                "Remove this report",
                key=f"remove_{index}",
            ):
                st.session_state.jobs.pop(
                    index
                )
                st.rerun()


if not status["running"]:
    if st.button(
        "+ Add Report",
        use_container_width=True,
    ):
        st.session_state.jobs.append(
            {
                "id": (
                    f"report_"
                    f"{int(time.time())}"
                ),
                "name": "New Report",
                "url": "",
                "action": "refresh",
                "selection": "",
                "selection_selector": "",
                "submit_selector": (
                    'button:has-text("SUBMIT")'
                ),
                "download_selector": (
                    'button[title="Download Excel"]'
                ),
                "wait_seconds": 2,
                "interval_minutes": 15,
                "destination": "",
                "filename_suffix": "",
                "filename_rule": "",
                "enabled": True,
            }
        )
        st.rerun()


st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button(
        "SAVE CONFIGURATION",
        use_container_width=True,
        disabled=status["running"],
    ):
        try:
            normalized_start = norm_time(
                start_time
            )
            normalized_stop = norm_time(
                stop_time
            )

            save(
                {
                    "start_time": normalized_start,
                    "stop_time": normalized_stop,
                    "jobs": st.session_state.jobs,
                }
            )

            st.session_state.start = (
                normalized_start
            )
            st.session_state.stop = (
                normalized_stop
            )

            st.success(
                "Configuration saved."
            )

        except Exception as error:
            st.error(str(error))

with col2:
    if st.button(
        "OPEN / LOGIN SESSION",
        use_container_width=True,
        disabled=status["running"],
    ):
        manager.cmd("open")
        time.sleep(0.4)
        st.rerun()

with col3:
    if st.button(
        "START DAILY RUN",
        type="primary",
        use_container_width=True,
        disabled=status["running"],
    ):
        try:
            normalized_start = norm_time(
                start_time
            )
            normalized_stop = norm_time(
                stop_time
            )

            bad = [
                job["name"]
                for job in st.session_state.jobs
                if job.get("enabled", True)
                and (
                    not job.get(
                        "url",
                        "",
                    ).strip()
                    or not job.get(
                        "destination",
                        "",
                    ).strip()
                )
            ]

            if bad:
                st.error(
                    "URL and destination required: "
                    + ", ".join(bad)
                )
            else:
                manager.cmd(
                    "start",
                    {
                        "start": normalized_start,
                        "stop": normalized_stop,
                        "jobs": st.session_state.jobs,
                    },
                )
                time.sleep(0.4)
                st.rerun()

        except Exception as error:
            st.error(str(error))

with col4:
    if st.button(
        "STOP NOW",
        use_container_width=True,
        disabled=not status["running"],
    ):
        manager.cmd("stop")
        time.sleep(0.4)
        st.rerun()


st.subheader("Status")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Browser",
    status["browser"],
)

col2.metric(
    "Run",
    "RUNNING"
    if status["running"]
    else "STOPPED",
)

col3.metric(
    "Next download",
    status["next_download"] or "-",
)

col4.metric(
    "Last download",
    status["last_download"] or "-",
)

st.info(status["message"])

st.caption(
    "Expiry selection remains under manual control. "
    "Credentials are not stored; the persistent Chromium "
    "profile keeps the normal login/session."
)

time.sleep(2)
st.rerun()
