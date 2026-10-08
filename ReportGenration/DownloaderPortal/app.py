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
    .block-container {padding-top:.45rem;padding-bottom:.7rem;max-width:1540px;margin:0 auto;}
    .portal-title {font-size:1.78rem;font-weight:850;line-height:1.04;margin-bottom:.04rem;}
    .portal-sub {color:#475569;font-size:.86rem;margin-bottom:.42rem;}
    .section-label {font-size:.76rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#475569;margin:.45rem 0 .28rem;}
    .dash-section-title {font-size:.78rem;font-weight:900;letter-spacing:.10em;color:#334155;margin:.58rem 0 .34rem;border-left:4px solid #2563eb;padding-left:.5rem;}

    .kpi-card {border-radius:.7rem;padding:.48rem .66rem;min-height:64px;border:1px solid rgba(71,85,105,.20);box-shadow:0 2px 5px rgba(15,23,42,.09);}
    .kpi-label {font-size:.70rem;font-weight:850;letter-spacing:.07em;color:#475569;}
    .kpi-value {font-size:1.48rem;font-weight:900;line-height:1.05;margin-top:.14rem;color:#0f172a;}
    .kpi-blue {background:linear-gradient(135deg,#dbeafe,#bfdbfe);border-left:5px solid #2563eb;}
    .kpi-cyan {background:linear-gradient(135deg,#cffafe,#a5f3fc);border-left:5px solid #0891b2;}
    .kpi-green {background:linear-gradient(135deg,#dcfce7,#bbf7d0);border-left:5px solid #16a34a;}
    .kpi-teal {background:linear-gradient(135deg,#ccfbf1,#99f6e4);border-left:5px solid #0d9488;}
    .kpi-amber {background:linear-gradient(135deg,#fef3c7,#fde68a);border-left:5px solid #d97706;}
    .kpi-red {background:linear-gradient(135deg,#ffe4e6,#fecdd3);border-left:5px solid #dc2626;}

    .smart-job {border:1px solid rgba(71,85,105,.22);border-radius:.68rem;padding:.62rem .70rem .52rem;min-height:112px;margin-bottom:.10rem;box-shadow:0 2px 5px rgba(15,23,42,.08);}
    .job-running {background:linear-gradient(135deg,#dcfce7,#f0fdf4);border-left:5px solid #16a34a;}
    .job-success {background:linear-gradient(135deg,#ccfbf1,#f0fdfa);border-left:5px solid #0d9488;}
    .job-partial {background:linear-gradient(135deg,#fef3c7,#fffbeb);border-left:5px solid #d97706;}
    .job-failed {background:linear-gradient(135deg,#fecdd3,#fff1f2);border-left:5px solid #dc2626;}
    .job-idle {background:linear-gradient(135deg,#e2e8f0,#f8fafc);border-left:5px solid #64748b;}

    .smart-top {display:flex;justify-content:space-between;align-items:center;gap:.4rem;}
    .smart-name {font-size:.94rem;font-weight:850;line-height:1.18;color:#0f172a;}
    .smart-badge {font-size:.65rem;font-weight:900;letter-spacing:.05em;padding:.20rem .42rem;border-radius:.4rem;background:rgba(15,23,42,.09);white-space:nowrap;color:#0f172a;}
    .smart-transport {font-size:.67rem;color:#475569;margin:.22rem 0 .34rem;font-weight:600;}
    .smart-activity {font-size:.73rem;line-height:1.30;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .smart-meta {display:flex;justify-content:space-between;gap:.35rem;margin-top:.34rem;font-size:.67rem;color:#475569;white-space:nowrap;overflow:hidden;font-weight:600;}
    .smart-meta span {overflow:hidden;text-overflow:ellipsis;}

    .rail-heading {font-size:.78rem;font-weight:900;letter-spacing:.10em;color:#0f172a;margin-bottom:.62rem;}
    .rail-label {font-size:.69rem;font-weight:900;letter-spacing:.07em;margin:.50rem 0 .28rem;}
    .rail-label.green {color:#15803d;}
    .rail-label.blue {color:#1d4ed8;}
    .rail-label.amber {color:#b45309;}
    .live-item {border-radius:.56rem;padding:.48rem .56rem;margin-bottom:.28rem;font-size:.72rem;line-height:1.28;border:1px solid rgba(71,85,105,.18);box-shadow:0 1px 3px rgba(15,23,42,.06);}
    .live-item b,.live-item span {display:block;}
    .live-item span {font-size:.66rem;color:#475569;margin-top:.10rem;}
    .live-item.running {background:#dcfce7;border-left:4px solid #16a34a;}
    .live-item.ready {background:#dbeafe;border-left:4px solid #2563eb;}
    .live-item.attention {background:#fef3c7;border-left:4px solid #d97706;}
    .rail-empty {border:1px dashed rgba(71,85,105,.28);border-radius:.55rem;padding:.46rem .56rem;color:#64748b;font-size:.67rem;margin-bottom:.55rem;background:#f8fafc;}

    div[data-testid="stButton"] > button {height:2.05rem;min-height:2.05rem;padding:.15rem .40rem;font-size:.74rem;font-weight:800;border-radius:.48rem;margin-bottom:.36rem;}
    div[data-testid="stMetric"] {padding:.10rem .28rem;}
    div[data-testid="stMetricLabel"] {font-size:.70rem;}
    div[data-testid="stMetricValue"] {font-size:1.12rem;}


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
    @st.fragment(run_every=2)
    def _render_smart_dashboard():
        snapshot = R["scheduler"].runtime_snapshot()
        active_meta = snapshot.get("active_meta", {}) if isinstance(snapshot, dict) else {}
        running_jobs, attention_jobs, ready_jobs = [], [], []

        for job in jobs:
            state = state_for(job)
            meta = active_meta.get(job["id"], {})
            is_running = state.state == "RUNNING" and job["id"] in R["scheduler"].active_job_ids
            if is_running:
                running_jobs.append((job, state, meta))
            elif state.state in {"FAILED", "PARTIAL"}:
                attention_jobs.append((job, state, meta))
            else:
                ready_jobs.append((job, state, meta))

        def short(value, limit=55):
            value = str(value or "").replace("\n", " ").strip()
            return value if len(value) <= limit else value[:limit - 3] + "..."

        counts = {
            "total": len(jobs),
            "enabled": sum(1 for j in jobs if bool(j.get("enabled", False))),
            "running": len(running_jobs),
            "success": sum(1 for j in jobs if state_for(j).state in {"SUCCESS", "COMPLETE"}),
            "partial": sum(1 for j in jobs if state_for(j).state == "PARTIAL"),
            "failed": sum(1 for j in jobs if state_for(j).state == "FAILED"),
        }

        kpi = st.columns(6, gap="small")
        cards = [
            ("TOTAL JOBS", counts["total"], "kpi-blue"),
            ("ENABLED", counts["enabled"], "kpi-cyan"),
            ("RUNNING", counts["running"], "kpi-green"),
            ("SUCCESS", counts["success"], "kpi-teal"),
            ("PARTIAL", counts["partial"], "kpi-amber"),
            ("FAILED", counts["failed"], "kpi-red"),
        ]
        for col, (label, value, cls) in zip(kpi, cards):
            with col:
                st.markdown(
                    f'<div class="kpi-card {cls}"><div class="kpi-label">{label}</div>'
                    f'<div class="kpi-value">{value}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="dash-section-title">JOB OPERATIONS</div>', unsafe_allow_html=True)
        main_col, rail_col = st.columns([3.55, 1.05], gap="medium")

        with main_col:
            for row_start in range(0, len(jobs), 3):
                row_jobs = jobs[row_start:row_start + 3]
                cols = st.columns(3, gap="small")
                for col, job in zip(cols, row_jobs):
                    with col:
                        state = state_for(job)
                        meta = active_meta.get(job["id"], {})
                        running = state.state == "RUNNING" and job["id"] in R["scheduler"].active_job_ids

                        if running:
                            status_class, icon, status_text = "job-running", "●", "RUNNING"
                        elif state.state in {"SUCCESS", "COMPLETE"}:
                            status_class, icon, status_text = "job-success", "✓", "SUCCESS"
                        elif state.state == "PARTIAL":
                            status_class, icon, status_text = "job-partial", "▲", "PARTIAL"
                        elif state.state == "FAILED":
                            status_class, icon, status_text = "job-failed", "✕", "FAILED"
                        else:
                            status_class, icon, status_text = "job-idle", "○", "IDLE"

                        stage = meta.get("stage") or state.current_stage or "IDLE"
                        activity = meta.get("detail") or state.current_detail or state.last_message or "Waiting"
                        result = state.processing_status or state.download_status or state.state or "—"
                        last = state.last_run or "—"
                        duration = f"{state.duration_seconds:.1f}s" if state.duration_seconds is not None else "—"
                        transport = job.get("transport", "Browser")

                        st.markdown(
                            f'<div class="smart-job {status_class}">'
                            f'<div class="smart-top"><div class="smart-name">{icon} {job.get("name", job["id"])}</div>'
                            f'<div class="smart-badge">{status_text}</div></div>'
                            f'<div class="smart-transport">{transport}</div>'
                            f'<div class="smart-activity"><b>{short(stage, 20)}</b> · {short(activity, 48)}</div>'
                            f'<div class="smart-meta"><span>Last {short(last, 22)}</span><span>{result}</span><span>{duration}</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        if st.button("RUN NOW", key=f"v9_run_{job['id']}", use_container_width=True):
                            try:
                                ok = R["scheduler"].manual_run(job["id"])
                                if ok:
                                    st.toast(f"Started: {job.get('name', job['id'])}")
                                else:
                                    st.warning("Job is already running.")
                            except Exception as exc:
                                st.error(f"Manual run failed: {exc}")

        with rail_col:
            st.markdown('<div class="rail-heading">LIVE OPERATIONS</div>', unsafe_allow_html=True)

            st.markdown('<div class="rail-label green">● RUNNING NOW</div>', unsafe_allow_html=True)
            if running_jobs:
                for job, state, meta in running_jobs:
                    st.markdown(
                        f'<div class="live-item running"><b>{job.get("name", job["id"])}</b>'
                        f'<span>{short(meta.get("stage") or state.current_stage or "RUNNING", 30)}</span>'
                        f'<span>{short(meta.get("detail") or state.current_detail or "Working", 42)}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown('<div class="rail-empty">No job running</div>', unsafe_allow_html=True)

            st.markdown('<div class="rail-label blue">○ READY / IDLE</div>', unsafe_allow_html=True)
            if ready_jobs:
                for job, state, meta in ready_jobs:
                    st.markdown(
                        f'<div class="live-item ready"><b>{job.get("name", job["id"])}</b>'
                        f'<span>{state.state} · every {job.get("interval_minutes", 5)}m</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown('<div class="rail-empty">No ready jobs</div>', unsafe_allow_html=True)

            st.markdown('<div class="rail-label amber">▲ ATTENTION</div>', unsafe_allow_html=True)
            if attention_jobs:
                for job, state, meta in attention_jobs:
                    st.markdown(
                        f'<div class="live-item attention"><b>{job.get("name", job["id"])}</b>'
                        f'<span>{state.state} · {short(state.last_error_category or state.current_detail or "Review", 40)}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown('<div class="rail-empty">No partial or failed jobs</div>', unsafe_allow_html=True)

        st.markdown('<div class="dash-section-title">RECENT ACTIVITY</div>', unsafe_allow_html=True)
        recent = sorted(status_rows(), key=lambda r: r["Last Run"] if r["Last Run"] != "—" else "", reverse=True)
        with st.expander("Open recent job results", expanded=False):
            st.dataframe(
                [
                    {"Job": r["Job"], "State": r["State"], "Stage": r["Stage"],
                     "Last": r["Last Run"], "Duration": r["Duration"],
                     "Result": r["Processing"], "Errors": r["Errors"]}
                    for r in recent
                ],
                use_container_width=True,
                hide_index=True,
                height=min(300, 55 + 34 * max(1, len(recent))),
            )

    _render_smart_dashboard()
with tab_jobs:
    st.markdown('<div class="section-label">Independent Job Control</div>', unsafe_allow_html=True)
    st.caption("Use the compact Overview for normal operation. Open a job only when configuration changes are needed.")

    for idx, job in enumerate(jobs):
        state = state_for(job)
        is_option = job.get("transport") == "optionchain_end_to_end"
        label = f"{'◉' if state.state == 'RUNNING' else '○'} {job.get('name', job['id'])}  ·  {state.state}"
        with st.expander(label, expanded=False):
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
