from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import streamlit as st

from runtime.config import ROOT, load_jobs, save_jobs, load_portal
from runtime.browser import BrowserManager
from runtime.discovery import discover
from runtime.validation import validate_job
from runtime.scheduler import Scheduler, normalize_job
from runtime.state import StateStore


st.set_page_config(
    page_title="Downloader Portal 9001",
    page_icon="⬢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.0rem; padding-bottom: 2rem;}
    .portal-title {font-size:2rem;font-weight:700;line-height:1.1;margin-bottom:.15rem;}
    .portal-sub {color:#6b7280;font-size:.92rem;margin-bottom:1rem;}
    .section-label {font-size:.78rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;margin:1rem 0 .45rem;}
    .job-note {padding:.55rem .75rem;border:1px solid rgba(128,128,128,.20);border-radius:.55rem;margin:.25rem 0 .55rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def runtime():
    portal = load_portal()
    profile = ROOT / portal.get("browser_profile", "browser_profile")
    return {
        "portal": portal,
        "browser": BrowserManager(profile),
        "loop": asyncio.new_event_loop(),
        "thread": None,
        "scheduler": None,
        "states": None,
    }


R = runtime()


def _legacy_reports_candidates() -> list[Path]:
    parent = ROOT.parent
    return [
        parent / "reports.json",
        parent / "config" / "reports.json",
        ROOT / "reports.json",
    ]


def _find_legacy_reports() -> Path | None:
    for path in _legacy_reports_candidates():
        if path.exists() and path.is_file():
            return path
    return None


def _normalise_legacy_job(raw: dict, idx: int) -> dict:
    j = dict(raw)
    j.setdefault("id", f"legacy_{idx + 1}")
    j.setdefault("name", j.get("report_name") or j["id"])
    j.setdefault("report_name", j["name"])
    j.setdefault("url", "")
    j.setdefault("transport", "browser_download")
    j.setdefault("browser_required", True)
    j.setdefault("browser_profile", "")
    j.setdefault("group_id", "legacy_8506")
    j.setdefault("scheduler_id", f"{j['id']}_scheduler")
    j["enabled"] = False
    j["environment"] = "TEST"
    j["test_live"] = "TEST"
    j.setdefault("action", "none")
    j.setdefault("selection", "")
    j.setdefault("selection_selector", "")
    j.setdefault("submit_selector", "")
    j.setdefault("download_selector", "")
    j.setdefault("wait_seconds", 2.0)
    j.setdefault("interval_minutes", 5)
    j.setdefault("timeout_seconds", 180)
    j.setdefault("retry_count", 1)
    j.setdefault("request_gap_ms", 750)
    j.setdefault("jitter_ms", 250)
    j.setdefault("batch_size", 20)
    j.setdefault("concurrency", 1)
    j.setdefault("backoff_initial_ms", 15000)
    j.setdefault("backoff_max_ms", 180000)
    j.setdefault("http_429_policy", "respect_retry_after_then_exponential_backoff")
    j.setdefault("expected_symbol_count", 0)
    destination = j.get("destination") or j.get("output_root") or ""
    j.setdefault("output_root", destination)
    j.setdefault("processing_root", "")
    j.setdefault("final_output_root", "")
    j.setdefault("filename_pattern", "{report_slug}_{timestamp}.xlsx")
    j.setdefault("filename_suffix", "")
    j.setdefault("filename_rule", "cycle_timestamp")
    j.setdefault("validation_required", True)
    j.setdefault("required_sheets", ["Data", "Status", "Run"])
    j.setdefault("alert_severity", "WARNING")
    j.setdefault("overlap_policy", "skip_if_previous_cycle_running")
    j["_source"] = "8506 reports.json"
    return j


def import_legacy_jobs() -> tuple[bool, str, list[dict]]:
    path = _find_legacy_reports()
    if path is None:
        return False, "No 8506 reports.json was found beside DownloaderPortal.", []
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if not isinstance(raw_jobs, list):
        return False, f"Unsupported reports.json structure: {path}", []
    imported = [
        _normalise_legacy_job(j, i)
        for i, j in enumerate(raw_jobs)
        if isinstance(j, dict)
    ]
    if not imported:
        return False, f"No report definitions found in {path}", []
    return True, str(path), imported


def run_loop():
    asyncio.set_event_loop(R["loop"])
    R["loop"].run_forever()


def ensure_loop():
    if R["thread"] is None or not R["thread"].is_alive():
        R["thread"] = threading.Thread(target=run_loop, daemon=True)
        R["thread"].start()


def submit(coro):
    ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, R["loop"])


def ensure_browser():
    return submit(R["browser"].start()).result(timeout=60)


jobs = load_jobs()
for job in jobs:
    normalize_job(job)

if R["states"] is None:
    R["states"] = StateStore(ROOT / "runtime" / "job_state.json")

if R["scheduler"] is None:
    R["scheduler"] = Scheduler(R["browser"], jobs, R["states"])

    async def _start_scheduler():
        await R["scheduler"].start_async()

    try:
        submit(_start_scheduler()).result(timeout=5)
    except Exception:
        pass


def state_for(job):
    return R["states"].get(job["id"])


def job_group(job):
    if job.get("id") == "optionchain_end_to_end" or job.get("group_id") == "specialized_collectors":
        return "Specialized Collectors"
    return "Legacy Downloaders"


def _live_row(job):
    s = state_for(job)
    meta = R["scheduler"].runtime_snapshot().get("active_meta", {}).get(job["id"], {})
    live = s.state == "RUNNING" and job["id"] in R["scheduler"].active_job_ids
    return {
        "Job": job.get("name", job["id"]),
        "Mode": "F&O Option Chain" if job.get("transport") == "optionchain_end_to_end" else job.get("transport", "Browser"),
        "State": s.state,
        "Stage": meta.get("stage") or s.current_stage or "—",
        "Activity": meta.get("detail") or s.current_detail or s.last_message or "—",
        "Heartbeat": s.heartbeat_at or "—",
        "Live": "YES" if live else "NO",
        "Last Run": s.last_run or "—",
        "Duration": f"{s.duration_seconds:.1f}s" if s.duration_seconds else "—",
        "Download": s.download_status or "—",
        "Processing": s.processing_status or "—",
        "Errors": s.error_count,
        "Last Error": s.last_error_category or "—",
    }


def status_rows():
    return [_live_row(job) for job in jobs]


st.markdown('<div class="portal-title">Downloader Portal <span style="font-size:.85rem;color:#6b7280;">9001</span></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="portal-sub">Advanced operational view · independent per-job scheduling · dedicated page isolation · 8506 remains untouched</div>',
    unsafe_allow_html=True,
)

@st.fragment(run_every=2)
def _render_live_metrics():
    states = [state_for(j) for j in jobs]
    running_count = sum(s.state == "RUNNING" and j["id"] in R["scheduler"].active_job_ids for j, s in zip(jobs, states))
    success_count = sum(s.state in {"SUCCESS", "COMPLETE"} for s in states)
    partial_count = sum(s.state == "PARTIAL" for s in states)
    failed_count = sum(s.state == "FAILED" for s in states)
    enabled_count = sum(bool(j.get("enabled")) for j in jobs)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Jobs", len(jobs))
    m2.metric("Enabled", enabled_count)
    m3.metric("Running", running_count)
    m4.metric("Success", success_count)
    m5.metric("Partial", partial_count)
    m6.metric("Failed", failed_count)

_render_live_metrics()

tab_overview, tab_jobs, tab_discovery, tab_runtime = st.tabs(
    ["Overview", "Job Control", "Discovery & Diagnostics", "Runtime Health"]
)

with st.sidebar:
    st.markdown("### Portal Controls")
    st.caption("TEST environment · port 9001")
    st.write(f"Registered jobs: **{len(jobs)}**")
    st.write(f"Scheduler: **{'RUNNING' if R['scheduler'].running else 'STOPPED'}**")

    if st.button("Open Authenticated Chromium", use_container_width=True):
        try:
            ensure_browser()
            page = submit(
                R["browser"].open_discovery_page(
                    "https://www.icharts.in/opt/OptionChain.php"
                )
            ).result(timeout=75)
            st.success(f"Chromium ready: {page.url}")
        except Exception as exc:
            st.error(f"Chromium open failed: {exc}")

    if st.button("Import 8506 Configuration (read-only)", use_container_width=True):
        try:
            ok, source, imported = import_legacy_jobs()
            if not ok:
                st.warning(source)
            else:
                existing_ids = {j.get("id") for j in jobs}
                added = 0
                for item in imported:
                    if item.get("id") not in existing_ids:
                        jobs.append(item)
                        added += 1
                save_jobs(jobs)
                R["scheduler"].refresh_jobs(jobs)
                st.success(f"Imported {added} new definitions. Imported jobs remain DISABLED/TEST.")
                st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.divider()
    st.caption("8506 production process is not controlled by this portal.")

with tab_overview:
    st.markdown('<div class="section-label">Live Job Board</div>', unsafe_allow_html=True)

    @st.fragment(run_every=2)
    def _render_live_job_board():
        for group in ["Specialized Collectors", "Legacy Downloaders"]:
            group_jobs = [j for j in jobs if job_group(j) == group]
            if not group_jobs:
                continue
            st.markdown(f"#### {group}")
            st.dataframe(
                [
                    {
                        "Job": j.get("name", j["id"]),
                        "Mode": "F&O Option Chain" if j.get("transport") == "optionchain_end_to_end" else "Browser Download",
                        "State": state_for(j).state,
                        "Stage": R["scheduler"].runtime_snapshot().get("active_meta", {}).get(j["id"], {}).get("stage") or state_for(j).current_stage or "—",
                        "Activity": R["scheduler"].runtime_snapshot().get("active_meta", {}).get(j["id"], {}).get("detail") or state_for(j).current_detail or "—",
                        "Heartbeat": state_for(j).heartbeat_at or "—",
                        "Last": state_for(j).last_run or "—",
                        "Next": state_for(j).next_run or "—",
                        "Errors": state_for(j).error_count,
                    }
                    for j in group_jobs
                ],
                use_container_width=True,
                hide_index=True,
            )

        recent = sorted(
            status_rows(),
            key=lambda r: r["Last Run"] if r["Last Run"] != "—" else "",
            reverse=True,
        )
        st.markdown("#### Current Job State")
        st.dataframe(recent, use_container_width=True, hide_index=True)

    _render_live_job_board()

    st.markdown('<div class="section-label">Operational Notes</div>', unsafe_allow_html=True)
    oc = next((j for j in jobs if j.get("transport") == "optionchain_end_to_end"), None)
    if oc:
        st.info(
            f"Option Chain is configured as a dedicated collector: "
            f"daily iCharts #optSymbol universe, one XLSX per cycle, "
            f"{oc.get('capture_concurrency',5)} capture / {oc.get('replay_concurrency',5)} replay workers, "
            f"250 ms request gap, 500 ms jitter and 5 s global 429 cooldown. "
            f"It remains TEST/DISABLED until explicitly enabled."
        )

with tab_jobs:
    st.markdown('<div class="section-label">Independent Job Control</div>', unsafe_allow_html=True)
    st.caption("Each job owns its own schedule, execution state, timeout, page and output path. There is no portal-wide execution semaphore.")

    for idx, job in enumerate(jobs):
        state = state_for(job)
        is_option = job.get("transport") == "optionchain_end_to_end"
        label = f"{'◉' if state.state == 'RUNNING' else '○'} {job.get('name', job['id'])}  ·  {state.state}"
        with st.expander(label, expanded=is_option and state.state in {"RUNNING", "PARTIAL", "FAILED"}):
            top1, top2, top3, top4 = st.columns([2.5, 2, 2, 1.3])
            with top1:
                st.markdown(f"**{job.get('report_name', job.get('name', job['id']))}**")
                st.caption(job.get("url", ""))
            with top2:
                st.write(f"Group: **{job.get('group_id','—')}**")
                st.write(f"Transport: **{job.get('transport','—')}**")
            with top3:
                sched = job.setdefault("schedule", {})
                st.write(
                    f"Schedule: **{sched.get('recurrence_minutes',5)} min** · "
                    f"{sched.get('start_time','09:25')}–{sched.get('stop_time','15:35')}"
                )
                st.write(f"Next: **{state.next_run or '—'}**")
            with top4:
                if st.button("Run Now", key=f"run_{idx}", use_container_width=True):
                    try:
                        ok = R["scheduler"].manual_run(job["id"])
                        if ok:
                            st.toast(f"Started: {job.get('name', job['id'])}")
                        else:
                            st.warning("Job is already running.")
                    except Exception as exc:
                        st.error(f"Manual run failed: {exc}")

            c1, c2, c3 = st.columns(3)
            with c1:
                job["enabled"] = st.toggle(
                    "Job Enabled",
                    bool(job.get("enabled")),
                    key=f"enabled_{idx}",
                )
                job["environment"] = st.selectbox(
                    "Environment",
                    ["TEST", "LIVE"],
                    index=0 if job.get("environment") != "LIVE" else 1,
                    key=f"env_{idx}",
                )
                job["timeout_seconds"] = st.number_input(
                    "Job Timeout (seconds)", 5, 3600,
                    int(job.get("timeout_seconds", 180)),
                    key=f"timeout_{idx}",
                )
            with c2:
                sched = job.setdefault("schedule", {})
                sched["enabled"] = st.toggle(
                    "Schedule Enabled",
                    bool(sched.get("enabled", job.get("enabled", False))),
                    key=f"sched_enabled_{idx}",
                )
                sched["start_time"] = st.text_input(
                    "Start", str(sched.get("start_time", "09:25")),
                    key=f"start_{idx}",
                )
                sched["stop_time"] = st.text_input(
                    "Stop", str(sched.get("stop_time", "15:35")),
                    key=f"stop_{idx}",
                )
                sched["recurrence_minutes"] = st.number_input(
                    "Every (minutes)", 1, 1440,
                    int(sched.get("recurrence_minutes", job.get("interval_minutes", 5))),
                    key=f"rec_{idx}",
                )
                days = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
                sched["days"] = st.multiselect(
                    "Trading Days", days,
                    default=[d for d in sched.get("days", days[:5]) if d in days],
                    key=f"days_{idx}",
                )
            with c3:
                job["output_root"] = st.text_input(
                    "Output Root",
                    job.get("output_root", job.get("destination", "")),
                    key=f"out_{idx}",
                )
                job["request_gap_ms"] = st.number_input(
                    "Request Gap (ms)", 0, 60000,
                    int(job.get("request_gap_ms", 750)),
                    key=f"gap_{idx}",
                )
                job["jitter_ms"] = st.number_input(
                    "Jitter (ms)", 0, 60000,
                    int(job.get("jitter_ms", 250)),
                    key=f"jitter_{idx}",
                )

            if is_option:
                st.markdown("**Option Chain Collector**")
                o1, o2, o3, o4, o5 = st.columns(5)
                with o1:
                    job["capture_concurrency"] = st.number_input(
                        "Capture Workers", 1, 10,
                        int(job.get("capture_concurrency", 5)),
                        key=f"oc_cap_{idx}",
                    )
                with o2:
                    job["replay_concurrency"] = st.number_input(
                        "Replay Workers", 1, 20,
                        int(job.get("replay_concurrency", 5)),
                        key=f"oc_rep_{idx}",
                    )
                with o3:
                    job["retry_count"] = st.number_input(
                        "429 Retries", 0, 10,
                        int(job.get("retry_count", 2)),
                        key=f"oc_retry_{idx}",
                    )
                with o4:
                    job["replay_429_cooldown_ms"] = st.number_input(
                        "429 Cooldown ms", 0, 60000,
                        int(job.get("replay_429_cooldown_ms", 5000)),
                        key=f"oc_cd_{idx}",
                    )
                with o5:
                    st.write("Universe")
                    st.success(
                        f"{'FROZEN DAILY' if job.get('freeze_universe_per_trading_day', True) else 'JOB LIST'}"
                    )
                st.caption(
                    "Universe source: authenticated iCharts #optSymbol. "
                    "The daily list is frozen and reused for subsequent cycles."
                )

            with st.expander("Advanced Job Configuration", expanded=False):
                a1, a2, a3 = st.columns(3)
                with a1:
                    job["name"] = st.text_input("Job Name", job.get("name", ""), key=f"name_{idx}")
                    job["report_name"] = st.text_input("Report Name", job.get("report_name", ""), key=f"report_{idx}")
                    st.text_input("Job ID", job["id"], disabled=True, key=f"id_{idx}")
                    st.text_input("Transport", job.get("transport", ""), disabled=True, key=f"transport_{idx}")
                with a2:
                    job["group_id"] = st.text_input("Group", job.get("group_id", ""), key=f"group_{idx}")
                    job["scheduler_id"] = st.text_input("Scheduler ID", job.get("scheduler_id", ""), key=f"scheduler_{idx}")
                    job["browser_profile"] = st.text_input("Browser Profile", job.get("browser_profile", ""), key=f"profile_{idx}")
                    job["page_isolation"] = st.checkbox("Dedicated Page", bool(job.get("page_isolation", True)), key=f"pageiso_{idx}")
                with a3:
                    job["backoff_initial_ms"] = st.number_input(
                        "Backoff Initial ms", 1000, 600000,
                        int(job.get("backoff_initial_ms", 15000)),
                        key=f"bo1_{idx}",
                    )
                    job["backoff_max_ms"] = st.number_input(
                        "Backoff Max ms", 1000, 1800000,
                        int(job.get("backoff_max_ms", 180000)),
                        key=f"bo2_{idx}",
                    )
                    job["http_429_policy"] = st.text_input(
                        "429 Policy",
                        job.get("http_429_policy", "respect_retry_after_then_exponential_backoff"),
                        key=f"429_{idx}",
                    )

            meta = R["scheduler"].runtime_snapshot().get("active_meta", {}).get(job["id"], {})
            st.caption(
                f"State: {state.state} · Stage: {meta.get('stage') or state.current_stage or '—'} · "
                f"Activity: {meta.get('detail') or state.current_detail or '—'} · "
                f"Heartbeat: {state.heartbeat_at or '—'} · "
                f"Last: {state.last_run or '—'} · Duration: {state.duration_seconds:.1f}s · "
                f"Download: {state.download_status or '—'} · Error: {state.last_error_category or '—'}"
            )

            errors = validate_job(job)
            if errors:
                st.warning("Configuration issues: " + "; ".join(errors))
            else:
                st.success("Configuration valid")

            s1, s2 = st.columns(2)
            with s1:
                if st.button("Save Job", key=f"save_{idx}", use_container_width=True):
                    normalize_job(job)
                    save_jobs(jobs)
                    R["scheduler"].refresh_jobs(jobs)
                    st.toast("Job saved")
            with s2:
                if st.button("Refresh Dashboard", key=f"refresh_{idx}", use_container_width=True):
                    st.rerun()

with tab_discovery:
    st.markdown('<div class="section-label">Discovery & Diagnostics</div>', unsafe_allow_html=True)

    d1, d2 = st.columns([2, 1])
    with d1:
        discover_url = st.text_input(
            "Report URL",
            "https://www.icharts.in/opt/OptionChain.php",
            key="discover_url",
        )
        discover_name = st.text_input("Report Name", "Option Chain", key="discover_name")
    with d2:
        st.write("Output root")
        st.code(
            r"D:\My-data\Share_P&L\Ichart Data\Screenshot\OptionChain",
            language="text",
        )

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Discover URL / DOM / Network", type="primary", use_container_width=True):
            try:
                ensure_browser()
                page = submit(
                    R["browser"].open_discovery_page(discover_url)
                ).result(timeout=75)
                result = submit(
                    discover(
                        page,
                        discover_url,
                        int(R["portal"]["discovery_timeout_seconds"] * 1000),
                    )
                ).result(timeout=70)
                st.session_state["discovery"] = result.to_dict()
                st.success("Discovery completed. Authenticated Chromium page remains open.")
            except Exception as exc:
                st.error(f"Discovery failed: {exc}")
    with b2:
        if st.button("Reload Current Job State", use_container_width=True):
            st.rerun()

    if "discovery" in st.session_state:
        with st.expander("Latest Discovery Result", expanded=False):
            st.json(st.session_state["discovery"])

    endpoint_path = ROOT / "config" / "OptionChain_Endpoint_Master.json"
    if endpoint_path.exists():
        with st.expander("Option Chain Endpoint Master", expanded=False):
            try:
                st.json(json.loads(endpoint_path.read_text(encoding="utf-8")))
            except Exception as exc:
                st.error(f"Endpoint master read failed: {exc}")
    else:
        st.info("OptionChain_Endpoint_Master.json is not installed in config yet.")

with tab_runtime:
    st.markdown('<div class="section-label">Runtime Health</div>', unsafe_allow_html=True)
    active = sorted(R["scheduler"].active_job_ids)
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Scheduler", "RUNNING" if R["scheduler"].running else "STOPPED")
    h2.metric("Active Jobs", len(active))
    h3.metric("Registered", len(jobs))
    h4.metric("Execution", "Independent")

    st.markdown("#### Active Jobs")
    if active:
        st.code("\n".join(active), language="text")
    else:
        st.success("No jobs currently running.")

    st.markdown("#### Runtime Policy")
    st.write(
        {
            "execution_model": "independent per-job scheduler tasks",
            "portal_wide_semaphore": False,
            "page_isolation": "shared authenticated context + dedicated page per job",
            "legacy_8506": "untouched",
            "environment": "TEST",
        }
    )
