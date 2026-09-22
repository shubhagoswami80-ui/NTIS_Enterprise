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
from runtime.optionchain_probe import run_parallel_probe
from runtime.optionchain_direct_probe import run_direct_post_probe
from runtime.strike_probe import run_strike_probe
from runtime.dynamic_params_probe import run_dynamic_params_probe
from runtime.optionchain_dynamic_state_probe import run_optionchain_dynamic_state_probe
from runtime.optionchain_request_capture_probe import run_optionchain_request_capture_probe
from runtime.optionchain_direct_replay_probe import run_optionchain_direct_replay_probe
from runtime.optionchain_direct_replay_probe_v2 import run_optionchain_direct_replay_probe_v2
from runtime.optionchain_end_to_end_collector_v3 import run_optionchain_end_to_end_collector_v3


st.set_page_config(page_title="Downloader Portal", layout="wide")


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
    j.setdefault("transport", j.get("transport") or "browser_download")
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
    imported = [_normalise_legacy_job(j, i) for i, j in enumerate(raw_jobs) if isinstance(j, dict)]
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

st.title("Downloader Portal")
st.caption("Controlled parallel downloader • legacy 8506 remains untouched")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Jobs", len(jobs))
m2.metric("Enabled", sum(bool(j.get("enabled")) for j in jobs))
m3.metric("Execution", "PARALLEL")
m4.metric("Legacy 8506", "UNTOUCHED")

st.divider()

with st.sidebar:
    st.header("Add / Discover Report")
    discover_url = st.text_input(
        "Report URL",
        "https://www.icharts.in/opt/OptionChain.php",
    )
    discover_name = st.text_input("Report name", "Option Chain")
    interval = st.number_input("Cycle interval (minutes)", min_value=1, value=5)
    output_root = st.text_input(
        "Output Root",
        r"D:\My-data\Share_P&L\Ichart Data\Screenshot\OptionChain",
    )
    st.caption("Only the root folder is configured here. Year/month/date are generated automatically.")

    if st.button("Open Chromium", use_container_width=True):
        try:
            ensure_browser()
            page = submit(R["browser"].open_discovery_page(discover_url)).result(timeout=75)
            st.success(f"Chromium opened on: {page.url}")
            st.info("If iCharts shows the Login page, enter your credentials in this browser window. The page remains open.")
        except Exception as exc:
            st.error(f"Chromium open failed: {exc}")

    if st.button("Import 8506 Report Configuration (read-only)", use_container_width=True):
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
                st.success(f"Imported {added} new report definitions from {source}. All imported jobs remain DISABLED/TEST.")
                st.rerun()
        except Exception as exc:
            st.error(f"8506 configuration import failed: {exc}")

    if st.button("Discover URL", type="primary", use_container_width=True):
        try:
            ensure_browser()
            page = submit(R["browser"].open_discovery_page(discover_url)).result(timeout=75)
            result = submit(
                discover(page, discover_url, int(R["portal"]["discovery_timeout_seconds"] * 1000))
            ).result(timeout=70)
            st.session_state["discovery"] = result.to_dict()
            final_url = str(result.to_dict().get("final_url", ""))
            if "login" in final_url.lower():
                st.warning("iCharts authentication is required. Enter credentials in Chromium, then Discover URL again.")
            else:
                st.success("Discovery completed. The authenticated browser page remains open.")
        except Exception as exc:
            st.error(f"Discovery failed: {exc}")

    st.divider()
    st.header("Option Chain Parallel Test")
    st.caption("Controlled test only. No production scheduler and no XLSX output.")
    test_symbols = st.text_input(
        "Symbols",
        "DIXON,RELIANCE",
        help="Start with 2 symbols. Increase only after the 2-symbol test passes.",
    )
    test_timeout = st.number_input("Per-symbol timeout (seconds)", 10, 120, 30)

    if st.button("Run Parallel Test", use_container_width=True):
        try:
            ensure_browser()
            symbols = [x.strip().upper() for x in test_symbols.split(",") if x.strip()]
            if len(symbols) < 2 or len(symbols) > 10:
                st.error("Controlled test accepts 2 to 10 symbols only.")
            else:
                with st.spinner(f"Running {len(symbols)} symbols in parallel..."):
                    result = submit(
                        run_parallel_probe(
                            R["browser"].context,
                            symbols,
                            int(test_timeout * 1000),
                        )
                    ).result(timeout=(test_timeout * len(symbols)) + 30)
                st.session_state["parallel_probe"] = result
                if result["failed"] == 0:
                    st.success(
                        f"Parallel probe PASS: {result['passed']}/{result['requested']} "
                        f"in {result['elapsed_ms']} ms."
                    )
                else:
                    st.warning(
                        f"Parallel probe PARTIAL: {result['passed']}/{result['requested']} passed "
                        f"in {result['elapsed_ms']} ms."
                    )
        except Exception as exc:
            st.error(f"Parallel test failed: {exc}")

st.divider()
st.header("Option Chain Direct POST Test")
st.caption("Controlled transport test only. No XLSX output is written.")
direct_symbols=st.text_input("Direct POST Symbols","DIXON,RELIANCE,INFY,TCS,HDFCBANK,ICICIBANK,SBIN,AXISBANK,LT,ITC,ITBEES,BAJFINANCE,KOTAKBANK,MARUTI,ADANIENT,ONGC,SUNPHARMA,WIPRO,HINDALCO,POWERGRID",help="Controlled validation: up to 20 symbols.")
direct_timeout=st.number_input("Direct POST timeout (seconds)",10,120,30,key="direct_timeout")
direct_concurrency=st.number_input("Direct POST concurrency",1,10,5,key="direct_concurrency")
st.info("Direct POST uses the authenticated Playwright browser context. Response bodies are inspected in memory only; no XLSX output is written.")
if st.button("Run Direct POST Test",use_container_width=True):
    try:
        symbols=[x.strip().upper() for x in direct_symbols.split(",") if x.strip()]
        if not 1<=len(symbols)<=20:
            st.error("Direct POST validation accepts 1 to 20 symbols.")
        else:
            with st.spinner(f"Testing direct POST for {len(symbols)} symbols..."):
                ensure_browser()
            result=submit(
                run_direct_post_probe(
                    context=R["browser"].context,
                    symbols=symbols,
                    timeout_seconds=int(direct_timeout),
                    concurrency=int(direct_concurrency),
                )
            ).result(timeout=(int(direct_timeout) * len(symbols)) + 30)
            st.session_state["direct_post_probe"]=result
            if result["failed"]==0:
                st.success(f"Direct POST PASS: {result['passed']}/{result['requested']} in {result['elapsed_ms']} ms.")
            else:
                st.warning(f"Direct POST diagnostic: {result['passed']}/{result['requested']} passed in {result['elapsed_ms']} ms.")

            # Immediate payload diagnostic: keep it directly under the test result
            # so the user does not need to scroll to the bottom of the portal.
            st.subheader("Immediate Payload Diagnostic")
            for rr in result.get("results", []):
                st.markdown(f"**{rr.get('symbol','')}** — {rr.get('status','')} / HTTP {rr.get('http_status','')}")
                st.json({
                    "symbol": rr.get("symbol"),
                    "attempts": rr.get("attempts"),
                    "elapsed_ms": rr.get("elapsed_ms"),
                    "json_valid": rr.get("json_valid"),
                    "iTotalRecords": rr.get("reported_total_records"),
                    "aaData_count": rr.get("aaData_count"),
                    "aaData_row_type": rr.get("aaData_row_type"),
                    "aaData_row_length": rr.get("aaData_row_length"),
                    "payload_structure": rr.get("payload_structure"),
                    "data_state": rr.get("data_state"),
                    "first_row_preview": rr.get("aaData_first_row_preview", []),
                    "error": rr.get("error", ""),
                })
    except Exception as exc:
        st.error(f"Direct POST test failed: {exc}")

st.divider()
st.header("Option Chain Mapped-Data Probe")
st.caption("Controlled extraction test: maps aaData[3:64] to the discovered 61 main-table columns. No XLSX or scheduler output is written.")
mapped_symbols=st.text_input("Mapped Probe Symbols","DIXON,RELIANCE,INFY,TCS,HDFCBANK",key="mapped_symbols")
mapped_concurrency=st.number_input("Mapped Probe concurrency",1,10,5,key="mapped_concurrency")
if st.button("Run Mapped Data Probe",use_container_width=True):
    try:
        symbols=[x.strip().upper() for x in mapped_symbols.split(",") if x.strip()]
        if not 1<=len(symbols)<=10:
            st.error("Mapped probe accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(f"Collecting and mapping {len(symbols)} symbols..."):
                result=submit(run_direct_post_probe(context=R["browser"].context, symbols=symbols, timeout_seconds=30, concurrency=int(mapped_concurrency))).result(timeout=(30*len(symbols))+30)
            st.session_state["mapped_probe"]=result
            st.success(f"Mapped probe: {result['passed']}/{result['requested']} PASS, {result.get('no_data',0)} NO_DATA, {result['failed']} FAILED in {result['elapsed_ms']} ms.")
            rows=[]
            for rr in result.get("results",[]):
                for mr in rr.get("mapped_rows",[]):
                    rows.append({"Symbol":rr.get("symbol"), **{k:v for k,v in mr.items() if k!="row_number"}, "Row":mr.get("row_number")})
            if rows:
                st.dataframe(rows, use_container_width=True, height=500)
            else:
                st.warning("No mapped rows returned.")
    except Exception as exc:
        st.error(f"Mapped data probe failed: {exc}")

st.subheader("Option Chain Dynamic Strike / Parameter Validation")
strike_symbols=st.text_input("Strike Probe Symbols","DIXON,RELIANCE,INFY,TCS,HDFCBANK",key="strike_symbols")
strike_concurrency=st.number_input("Strike Probe concurrency",1,10,5,key="strike_concurrency")
if st.button("Run Dynamic Strike / Parameter Validation",use_container_width=True):
    symbols=[x.strip().upper() for x in strike_symbols.split(",") if x.strip()]
    if not symbols or len(symbols)>10:
        st.error("Strike probe accepts 1 to 10 symbols.")
    else:
        try:
            with st.spinner(f"Discovering dynamic strike/expiry and validating direct POST for {len(symbols)} symbols..."):
                result=submit(run_strike_probe(context=R["browser"].context,symbols=symbols,timeout_seconds=15,concurrency=int(strike_concurrency))).result(timeout=(15*len(symbols))+30)
            st.success(f"Dynamic strike validation: {result['passed']}/{result['requested']} PASS, {result['failed']} FAILED in {result['elapsed_ms']} ms.")
            st.json(result["results"])
        except Exception as exc:
            st.error(f"Strike / parameter probe failed: {exc}")

st.subheader("Option Chain Dynamic Parameters Probe")
st.caption("Controlled endpoint inspection only. Determines whether symbol-specific expiry/strike/date parameters can be obtained without loading a separate browser page. No XLSX or scheduler output is written.")
dyn_symbols=st.text_input("Dynamic Parameter Symbols","DIXON,RELIANCE,INFY,TCS,HDFCBANK",key="dyn_symbols")
dyn_concurrency=st.number_input("Dynamic Parameter concurrency",1,10,5,key="dyn_concurrency")
if st.button("Run Dynamic Parameters Probe",use_container_width=True):
    try:
        symbols=[x.strip().upper() for x in dyn_symbols.split(",") if x.strip()]
        if not 1<=len(symbols)<=10:
            st.error("Dynamic parameter probe accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(f"Inspecting symbol parameters for {len(symbols)} symbols..."):
                result=submit(run_dynamic_params_probe(context=R["browser"].context, symbols=symbols, timeout_seconds=15, concurrency=int(dyn_concurrency))).result(timeout=(15*len(symbols))+30)
            st.session_state["dynamic_params_probe"]=result
            st.success(f"Dynamic parameter probe: {result['passed']}/{result['requested']} PASS, {result['failed']} FAILED in {result['elapsed_ms']} ms.")
            compact=[]
            for r in result.get("results",[]):
                compact.append({"Symbol":r.get("symbol"),"HTTP":r.get("http_status"),"JSON":r.get("json_valid"),"ms":r.get("elapsed_ms"),"Candidate fields":json.dumps(r.get("candidate_fields",{}),default=str),"Error":r.get("error","")})
            st.dataframe(compact,use_container_width=True,hide_index=True)
            for r in result.get("results",[]):
                with st.expander(f"{r.get('symbol')} — response details"):
                    st.json(r)
    except Exception as exc:
        st.error(f"Dynamic parameter probe failed: {exc}")


st.subheader("Option Chain Dynamic State → Direct POST Probe")
st.caption(
    "TEST ONLY. Uses the existing authenticated context, changes the iCharts "
    "symbol selector through the page's own control, reads the resulting "
    "dynamic parameters, then validates the direct POST request."
)
state_symbols = st.text_input(
    "Dynamic State Symbols",
    "DIXON,RELIANCE,INFY,TCS,HDFCBANK",
    key="state_symbols",
)

if st.button("Run Dynamic State → Direct POST Probe", use_container_width=True):
    try:
        symbols = [x.strip().upper() for x in state_symbols.split(",") if x.strip()]
        if not 1 <= len(symbols) <= 10:
            st.error("Dynamic State probe accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(
                f"Resolving iCharts page state for {len(symbols)} symbols..."
            ):
                result = submit(
                    run_optionchain_dynamic_state_probe(
                        context=R["browser"].context,
                        symbols=symbols,
                        timeout_seconds=30,
                    )
                ).result(timeout=(30 * len(symbols)) + 60)

            st.session_state["dynamic_state_probe"] = result
            if result["failed"] == 0:
                st.success(
                    f"Dynamic State probe PASS: {result['passed']}/{result['requested']} "
                    f"in {result['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"Dynamic State probe PARTIAL: {result['passed']}/{result['requested']} "
                    f"passed in {result['elapsed_ms']} ms."
                )

            compact = []
            for r in result.get("results", []):
                compact.append({
                    "Requested": r.get("symbol"),
                    "Selected": r.get("selected_symbol"),
                    "Expiry": r.get("optExpDate"),
                    "ATM": r.get("strikePriceATM"),
                    "Central": r.get("centralStrike"),
                    "optStrike": r.get("optStrike"),
                    "7 Rows": r.get("aaData_count"),
                    "Table HTTP": r.get("table_http"),
                    "Server Symbol": r.get("server_symbol"),
                    "POST Valid": r.get("post_valid"),
                    "Pass": r.get("pass"),
                    "ms": r.get("elapsed_ms"),
                    "Error": r.get("error", ""),
                })
            if compact:
                st.dataframe(compact, use_container_width=True, hide_index=True)
            for r in result.get("results", []):
                with st.expander(f"{r.get('symbol')} — dynamic state details"):
                    st.json(r)
    except Exception as exc:
        st.error(f"Dynamic State probe failed: {exc}")


st.subheader("Option Chain Actual Request Capture Probe")
st.caption(
    "TEST ONLY. Uses the authenticated iCharts page selector and captures the "
    "actual OptionChainTable POST generated by iCharts. No manual POST replay."
)
capture_symbols = st.text_input(
    "Capture Symbols",
    "DIXON,RELIANCE,INFY,TCS,HDFCBANK",
    key="capture_symbols",
)

if st.button("Run Actual Request Capture Probe", use_container_width=True):
    try:
        symbols = [x.strip().upper() for x in capture_symbols.split(",") if x.strip()]
        if not 1 <= len(symbols) <= 10:
            st.error("Request Capture probe accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(
                f"Capturing iCharts-generated requests for {len(symbols)} symbols..."
            ):
                result = submit(
                    run_optionchain_request_capture_probe(
                        context=R["browser"].context,
                        symbols=symbols,
                        timeout_seconds=30,
                    )
                ).result(timeout=(30 * len(symbols)) + 90)

            st.session_state["request_capture_probe"] = result
            if result["failed"] == 0:
                st.success(
                    f"Actual Request Capture PASS: {result['passed']}/{result['requested']} "
                    f"in {result['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"Actual Request Capture PARTIAL: {result['passed']}/{result['requested']} "
                    f"passed in {result['elapsed_ms']} ms."
                )

            compact = []
            for r in result.get("results", []):
                compact.append({
                    "Requested": r.get("symbol"),
                    "Selected": r.get("selected_symbol"),
                    "Request HTTP": r.get("request_http"),
                    "Request URL": r.get("request_url"),
                    "Expiry": r.get("captured_expiry"),
                    "optStrike": r.get("captured_optStrike"),
                    "ATM": r.get("response_ATM"),
                    "Returned Rows": r.get("response_rows"),
                    "Returned Strikes": ", ".join(r.get("returned_strikes", [])),
                    "Server Symbol": r.get("server_symbol"),
                    "ATM In Returned Strikes": r.get("atm_in_returned_strikes"),
                    "Pass": r.get("pass"),
                    "ms": r.get("elapsed_ms"),
                    "Error": r.get("error", ""),
                })
            if compact:
                st.dataframe(compact, use_container_width=True, hide_index=True)

            for r in result.get("results", []):
                with st.expander(f"{r.get('symbol')} — captured request details"):
                    st.json(r)
    except Exception as exc:
        st.error(f"Actual Request Capture probe failed: {exc}")


st.subheader("Option Chain Captured Request → Direct Replay Probe")
st.caption(
    "TEST ONLY. Captures the real iCharts-generated request for each symbol, "
    "then replays that exact request through the authenticated context and "
    "compares the returned Option Chain payload."
)
replay_symbols = st.text_input(
    "Replay Symbols",
    "DIXON,RELIANCE,INFY,TCS,HDFCBANK",
    key="replay_symbols",
)

if st.button("Run Captured Request → Direct Replay Probe", use_container_width=True):
    try:
        symbols = [x.strip().upper() for x in replay_symbols.split(",") if x.strip()]
        if not 1 <= len(symbols) <= 10:
            st.error("Direct Replay probe accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(
                f"Capturing and directly replaying requests for {len(symbols)} symbols..."
            ):
                result = submit(
                    run_optionchain_direct_replay_probe(
                        context=R["browser"].context,
                        symbols=symbols,
                        timeout_seconds=30,
                    )
                ).result(timeout=(30 * len(symbols)) + 120)

            st.session_state["direct_replay_probe"] = result
            if result["failed"] == 0:
                st.success(
                    f"Direct Replay PASS: {result['passed']}/{result['requested']} "
                    f"in {result['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"Direct Replay PARTIAL: {result['passed']}/{result['requested']} "
                    f"passed in {result['elapsed_ms']} ms."
                )

            compact = []
            for r in result.get("results", []):
                compact.append({
                    "Symbol": r.get("symbol"),
                    "Captured HTTP": r.get("captured_http"),
                    "Replay HTTP": r.get("replay_http"),
                    "Captured Server": r.get("captured_server_symbol"),
                    "Replay Server": r.get("replay_server_symbol"),
                    "Captured ATM": r.get("captured_atm"),
                    "Replay ATM": r.get("replay_atm"),
                    "Captured Rows": r.get("captured_rows"),
                    "Replay Rows": r.get("replay_rows"),
                    "Payload Match": r.get("payload_match"),
                    "Pass": r.get("pass"),
                    "ms": r.get("elapsed_ms"),
                    "Error": r.get("error", ""),
                })
            if compact:
                st.dataframe(compact, use_container_width=True, hide_index=True)

            for r in result.get("results", []):
                with st.expander(f"{r.get('symbol')} — replay details"):
                    st.json(r)
    except Exception as exc:
        st.error(f"Direct Replay probe failed: {exc}")


st.subheader("Option Chain Direct Replay Probe v2 — Correct Symbol Capture")
st.caption(
    "Fixes background/initial Option Chain requests by accepting only the "
    "POST whose optSymbol exactly matches the requested symbol."
)
replay_v2_symbols = st.text_input(
    "Replay v2 Symbols",
    "DIXON,RELIANCE,INFY,TCS,HDFCBANK",
    key="replay_v2_symbols",
)

if st.button(
    "Run Direct Replay Probe v2 — Correct Symbol Capture",
    use_container_width=True,
):
    try:
        symbols = [
            x.strip().upper()
            for x in replay_v2_symbols.split(",")
            if x.strip()
        ]
        if not 1 <= len(symbols) <= 10:
            st.error("Direct Replay v2 accepts 1 to 10 symbols.")
        else:
            ensure_browser()
            with st.spinner(
                f"Capturing symbol-specific requests for {len(symbols)} symbols..."
            ):
                result = submit(
                    run_optionchain_direct_replay_probe_v2(
                        context=R["browser"].context,
                        symbols=symbols,
                        timeout_seconds=30,
                    )
                ).result(timeout=(30 * len(symbols)) + 120)

            st.session_state["direct_replay_probe_v2"] = result
            if result["failed"] == 0:
                st.success(
                    f"Direct Replay v2 PASS: {result['passed']}/{result['requested']} "
                    f"in {result['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"Direct Replay v2 PARTIAL: {result['passed']}/{result['requested']} "
                    f"passed in {result['elapsed_ms']} ms."
                )

            compact = []
            for r in result.get("results", []):
                compact.append({
                    "Requested": r.get("symbol"),
                    "Captured optSymbol": r.get("captured_optSymbol"),
                    "Captured Server": r.get("captured_server_symbol"),
                    "Replay Server": r.get("replay_server_symbol"),
                    "Captured ATM": r.get("captured_atm"),
                    "Replay ATM": r.get("replay_atm"),
                    "Captured Rows": r.get("captured_rows"),
                    "Replay Rows": r.get("replay_rows"),
                    "Payload Match": r.get("payload_match"),
                    "Pass": r.get("pass"),
                    "ms": r.get("elapsed_ms"),
                    "Error": r.get("error", ""),
                })
            if compact:
                st.dataframe(compact, use_container_width=True, hide_index=True)

            for r in result.get("results", []):
                with st.expander(f"{r.get('symbol')} — v2 capture details"):
                    st.json(r)
    except Exception as exc:
        st.error(f"Direct Replay v2 failed: {exc}")


st.subheader("Option Chain End-to-End Collector — Benchmark")
st.caption(
    "Controlled end-to-end test: capture each symbol's real iCharts request, "
    "direct-replay it with 429 protection, map the 70-field payload to the "
    "61-column Option Chain view, and write ONE final XLSX. No scheduler."
)

collector_default_symbols = (
    "DIXON,RELIANCE,INFY,TCS,HDFCBANK,ONGC,SUNPHARMA,HINDALCO,POWERGRID,"
    "SBIN,ICICIBANK,AXISBANK,KOTAKBANK,LT,ITC,ADANIENT,MARUTI,TMPV,"
    "BHARTIARTL,BAJFINANCE"
)

collector_symbols = st.text_area(
    "Collector Symbols",
    collector_default_symbols,
    height=90,
    key="collector_symbols",
)
collector_concurrency = st.number_input(
    "Direct replay concurrency", 1, 10, 5, key="collector_concurrency"
)
collector_output_root = st.text_input(
    "Collector output root",
    r"D:\My-data\Share_P&L\Ichart Data\Screenshot\OptionChain",
    key="collector_output_root",
)

if st.button(
    "Run 20-Symbol End-to-End Collection + Final XLSX",
    use_container_width=True,
):
    try:
        symbols = [x.strip().upper() for x in collector_symbols.split(",") if x.strip()]
        if len(symbols) != 20:
            st.error(
                f"This benchmark requires exactly 20 symbols. Current count: {len(symbols)}."
            )
        else:
            ensure_browser()
            with st.spinner(
                "Running 20-symbol capture → direct replay → final XLSX..."
            ):
                future = submit(
                    run_optionchain_end_to_end_collector_v3(
                        context=R["browser"].context,
                        symbols=symbols,
                        output_root=collector_output_root,
                        replay_concurrency=int(collector_concurrency),
                        timeout_seconds=30,
                        max_retries=2,
                        backoff_initial_ms=1500,
                        backoff_max_ms=15000,
                        request_gap_ms=100,
                        jitter_ms=100,
                    )
                )
                result = future.result(timeout=20 * 45 + 180)

            st.session_state["collector_result"] = result

            if result["failed"] == 0:
                st.success(
                    f"20-symbol collection v2 PASS: "
                    f"{result['passed']}/{result['requested']} "
                    f"in {result['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"20-symbol collection v2 PARTIAL: "
                    f"{result['passed']}/{result['requested']} "
                    f"passed in {result['elapsed_ms']} ms."
                )

            st.write(f"**Final workbook:** `{result.get('output_file', '')}`")
            st.write(
                f"Data rows: **{result.get('data_rows', 0)}** | "
                f"Passed: **{result.get('passed', 0)}** | "
                f"No data: **{result.get('no_data', 0)}** | "
                f"Failed: **{result.get('failed', 0)}**"
            )

            compact = []
            for r in result.get("results", []):
                compact.append(
                    {
                        "Symbol": r.get("symbol"),
                        "HTTP": r.get("replay_http"),
                        "Expiry": r.get("expiry"),
                        "ATM": r.get("atm"),
                        "Rows": r.get("rows"),
                        "Status": r.get("status"),
                        "Capture ms": r.get("capture_ms"),
                        "Replay ms": r.get("replay_ms"),
                        "Error": r.get("error", ""),
                    }
                )
            if compact:
                st.dataframe(
                    compact,
                    use_container_width=True,
                    hide_index=True,
                )
    except Exception as exc:
        st.error(f"20-symbol collector v2 failed: {exc}")

st.subheader("Registered Jobs")

if not jobs:
    st.info("No jobs registered.")
else:
    for idx, job in enumerate(jobs):
        with st.expander(
            f"{idx + 1}. {job.get('name', job['id'])} — {job.get('transport', '')}",
            expanded=(idx == 0),
        ):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Job ID", job["id"], disabled=True, key=f"id_{idx}")
                job["name"] = st.text_input("Job Name", job.get("name", ""), key=f"name_{idx}")
                job["report_name"] = st.text_input("Report Name", job.get("report_name", ""), key=f"report_{idx}")
                job["url"] = st.text_input("URL", job.get("url", ""), key=f"url_{idx}")
                job["transport"] = st.text_input("Transport", job.get("transport", ""), key=f"transport_{idx}")
                job["group_id"] = st.text_input("Group", job.get("group_id", ""), key=f"group_{idx}")
                job["scheduler_id"] = st.text_input("Scheduler", job.get("scheduler_id", ""), key=f"scheduler_{idx}")
                job["environment"] = st.selectbox(
                    "Environment", ["TEST", "LIVE"], index=0 if job.get("environment") != "LIVE" else 1,
                    key=f"env_{idx}"
                )
            with c2:
                job["enabled"] = st.checkbox("Enabled", bool(job.get("enabled")), key=f"enabled_{idx}")
                job["browser_required"] = st.checkbox("Browser Required", bool(job.get("browser_required")), key=f"browser_{idx}")
                job["interval_minutes"] = st.number_input("Interval (minutes)", 1, 1440, int(job.get("interval_minutes", 5)), key=f"interval_{idx}")
                job["wait_seconds"] = st.number_input("Wait Seconds", 0.0, 120.0, float(job.get("wait_seconds", 2)), key=f"wait_{idx}")
                job["timeout_seconds"] = st.number_input("Timeout Seconds", 5, 3600, int(job.get("timeout_seconds", 180)), key=f"timeout_{idx}")
                job["retry_count"] = st.number_input("Retry Count", 0, 10, int(job.get("retry_count", 1)), key=f"retry_{idx}")
                job["concurrency"] = st.number_input("Request Concurrency", 1, 50, int(job.get("concurrency", 8)), key=f"conc_{idx}")
                job["batch_size"] = st.number_input("Batch Size", 1, 500, int(job.get("batch_size", 20)), key=f"batch_{idx}")
                job["expected_symbol_count"] = st.number_input("Expected Symbols/Records", 0, 10000, int(job.get("expected_symbol_count", 0)), key=f"expected_{idx}")

            st.markdown("**Execution / rate-limit controls**")
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                job["request_gap_ms"] = st.number_input("Request Gap ms", 0, 60000, int(job.get("request_gap_ms", 750)), key=f"gap_{idx}")
            with e2:
                job["jitter_ms"] = st.number_input("Jitter ms", 0, 60000, int(job.get("jitter_ms", 250)), key=f"jitter_{idx}")
            with e3:
                job["backoff_initial_ms"] = st.number_input("Backoff Initial ms", 1000, 600000, int(job.get("backoff_initial_ms", 15000)), key=f"bo1_{idx}")
            with e4:
                job["backoff_max_ms"] = st.number_input("Backoff Max ms", 1000, 1800000, int(job.get("backoff_max_ms", 180000)), key=f"bo2_{idx}")

            st.markdown("**Browser / action controls**")
            b1, b2, b3 = st.columns(3)
            with b1:
                actions = ["none", "refresh", "submit", "refresh_submit", "radio_submit", "radio"]
                current_action = job.get("action", "none")
                if current_action not in actions:
                    current_action = "none"
                job["action"] = st.selectbox("Action", actions, index=actions.index(current_action), key=f"action_{idx}")
                job["selection"] = st.text_input("Selection", job.get("selection", ""), key=f"sel_{idx}")
            with b2:
                job["selection_selector"] = st.text_input("Selection Selector", job.get("selection_selector", ""), key=f"ss_{idx}")
                job["submit_selector"] = st.text_input("Submit Selector", job.get("submit_selector", ""), key=f"sub_{idx}")
            with b3:
                job["download_selector"] = st.text_input("Download Selector", job.get("download_selector", ""), key=f"dl_{idx}")
                job["browser_profile"] = st.text_input("Browser Profile", job.get("browser_profile", ""), key=f"profile_{idx}")

            st.markdown("**Output / processing controls**")
            job["output_root"] = st.text_input("Output Root", job.get("output_root", ""), key=f"out_{idx}")
            st.caption("Final path: `<root>\\<year>\\<month_name>\\<date>\\<report>_<timestamp>.xlsx`")
            p1, p2, p3 = st.columns(3)
            with p1:
                job["processing_root"] = st.text_input("Processing Root", job.get("processing_root", ""), key=f"proc_{idx}")
            with p2:
                job["final_output_root"] = st.text_input("Final Output Root", job.get("final_output_root", ""), key=f"final_{idx}")
            with p3:
                job["filename_rule"] = st.text_input("Filename Rule", job.get("filename_rule", ""), key=f"frule_{idx}")

            st.markdown("**Validation / alert controls**")
            v1, v2, v3 = st.columns(3)
            with v1:
                job["validation_required"] = st.checkbox("Validation Required", bool(job.get("validation_required", True)), key=f"valid_{idx}")
            with v2:
                severities = ["INFO","WARNING","ERROR","CRITICAL"]
                current_severity = job.get("alert_severity","WARNING")
                if current_severity not in severities:
                    current_severity = "WARNING"
                job["alert_severity"] = st.selectbox("Alert Severity", severities, index=severities.index(current_severity), key=f"alert_{idx}")
            with v3:
                job["http_429_policy"] = st.text_input("HTTP 429 Policy", job.get("http_429_policy",""), key=f"429_{idx}")

            errors = validate_job(job)
            if errors:
                st.warning("Configuration issues: " + "; ".join(errors))
            else:
                st.success("Configuration valid")

            if st.button("Save Job Configuration", key=f"save_{idx}"):
                save_jobs(jobs)
                st.success("Saved.")

st.divider()

if "discovery" in st.session_state:
    st.subheader("Latest URL Discovery")
    st.json(st.session_state["discovery"])

if "parallel_probe" in st.session_state:
    st.subheader("Latest Option Chain Parallel Test")
    st.json(st.session_state["parallel_probe"])

if "direct_post_probe" in st.session_state:
    st.subheader("Latest Option Chain Direct POST Test")
    probe = st.session_state["direct_post_probe"]
    st.json(probe)
    results = probe.get("results", []) if isinstance(probe, dict) else []
    if results:
        st.markdown("**Compact diagnostic**")
        compact = []
        for r in results:
            compact.append({
                "Symbol": r.get("symbol"), "Status": r.get("status"), "HTTP": r.get("http_status"),
                "Attempts": r.get("attempts"), "ms": r.get("elapsed_ms"), "aaData": r.get("aaData_count"),
                "Reported": r.get("reported_total_records"), "Row Type": r.get("aaData_row_type"),
                "Row Length": r.get("aaData_row_length"), "Payload": r.get("payload_structure"),
                "Error": r.get("error", ""),
            })
        st.dataframe(compact, use_container_width=True, hide_index=True)
        shape = next((r for r in results if r.get("status") == "PASS" and r.get("aaData_count", 0) > 0), None)
        if shape:
            st.markdown("**First successful payload shape**")
            st.write({
                "symbol": shape.get("symbol"), "aaData_count": shape.get("aaData_count"),
                "reported_total_records": shape.get("reported_total_records"),
                "aaData_row_type": shape.get("aaData_row_type"),
                "aaData_row_length": shape.get("aaData_row_length"),
                "first_row_preview": shape.get("aaData_first_row_preview", []),
            })

st.info(
    "Option Chain remains TEST/DISCOVERY. The parallel probe exercises the authenticated browser "
    "request mechanism only; it does not activate the production scheduler or write consumer reports."
)


st.divider()
st.subheader("Option Chain — Variable-Size Parallel Capture Benchmark + Failure Diagnostics")
st.caption(
    "Controlled 50-symbol benchmark: dedicated browser pages capture the real "
    "iCharts request in parallel, then authenticated direct POST replay runs "
    "concurrently and ONE final XLSX is written. No scheduler."
)

collector_variable_default = """DIXON,RELIANCE,INFY,TCS,HDFCBANK,ONGC,SUNPHARMA,HINDALCO,POWERGRID,SBIN,ICICIBANK,AXISBANK,KOTAKBANK,LT,ITC,ADANIENT,MARUTI,TMPV,BHARTIARTL,BAJFINANCE,BAJAJFINSV,ADANIPORTS,ASIANPAINT,APOLLOHOSP,BAJAJ-AUTO,BEL,BPCL,CIPLA,COALINDIA,COFORGE,DRREDDY,EICHERMOT,GRASIM,HCLTECH,HINDZINC,JSWSTEEL,NTPC,PIDILITIND,PNB,RECLTD,SBILIFE,SHRIRAMFIN,TATACONSUM,TATASTEEL,TECHM,TITAN,ULTRACEMCO,WIPRO,M&M,HEROMOTOCO,INDIGO,JINDALSTEL,JUBLFOOD,LICHSGFIN,LUPIN,MANAPPURAM,MCX,MUTHOOTFIN,NATIONALUM,NAUKRI,OBEROIRLTY,OFSS,PAGEIND,PATANJALI,PEL,PERSISTENT,PIIND,POLYCAB,SAIL,SAMMAANCAP,SIEMENS,SOLARINDS,SRF,SUNTV,SUPREMEIND,TATACHEM,TATACOMM,TATAELXSI,TRENT,TVSMOTOR,UNOMINDA,UPL,VEDL,VOLTAS,ZYDUSLIFE,AMBUJACEM,AUROPHARMA,BANDHANBNK,BANKBARODA,CANBK,CHOLAFIN,CONCOR,DALBHARAT,FEDERALBNK,IDFCFIRSTB,IRCTC,INDIANB,BANKINDIA,IEX,PFC"""

collector_variable_symbols = st.text_area(
    "Symbol list (no fixed count limit)",
    collector_variable_default,
    height=90,
    key="collector_variable_symbols",
)
collector_variable_capture_concurrency = st.number_input(
    "Browser capture concurrency",
    min_value=1,
    max_value=10,
    value=5,
    step=1,
    key="collector_variable_capture_concurrency",
)
collector_variable_replay_concurrency = st.number_input(
    "Direct replay concurrency",
    min_value=1,
    max_value=20,
    value=5,
    step=1,
    key="collector_variable_replay_concurrency",
)

if st.button(
    "Run Variable-Size Parallel-Capture Benchmark",
    use_container_width=True,
    key="run_variable_parallel_capture",
):
    symbols_50 = [
        x.strip().upper()
        for x in collector_variable_symbols.split(",")
        if x.strip()
    ]
    if not symbols_50 or len(symbols_50) != len(set(symbols_50)):
        st.error(
            f"Enter at least 1 unique symbol, with no duplicates. "
            f"Current count: {len(symbols_50)}."
        )
    else:
        try:
            ensure_browser()
            with st.spinner(
                "Running 50-symbol parallel capture → direct replay → final XLSX..."
            ):
                future_50 = submit(
                    run_optionchain_end_to_end_collector_v3(
                        context=R["browser"].context,
                        symbols=symbols_50,
                        output_root=collector_output_root,
                        replay_concurrency=int(collector_variable_replay_concurrency),
                        capture_concurrency=int(collector_variable_capture_concurrency),
                        timeout_seconds=30,
                        max_retries=2,
                        backoff_initial_ms=1500,
                        backoff_max_ms=15000,
                        request_gap_ms=100,
                        jitter_ms=100,
                    )
                )
                result_50 = future_50.result(timeout=max(300, len(symbols_50) * 45 + 300))

            if result_50["failed"] == 0:
                st.success(
                    f"Variable-size parallel-capture PASS: "
                    f"{result_50['passed']}/{result_50['requested']} "
                    f"in {result_50['elapsed_ms']} ms."
                )
            else:
                st.warning(
                    f"Variable-size parallel-capture PARTIAL: "
                    f"{result_50['passed']}/{result_50['requested']} "
                    f"in {result_50['elapsed_ms']} ms."
                )

            st.write(f"**Final workbook:** `{result_50.get('output_file', '')}`")
            st.write(
                f"Data rows: **{result_50.get('data_rows', 0)}** | "
                f"Passed: **{result_50.get('passed', 0)}** | "
                f"No data: **{result_50.get('no_data', 0)}** | "
                f"Failed: **{result_50.get('failed', 0)}**"
            )
            if result_50.get("status_rows"):
                st.dataframe(result_50["status_rows"], use_container_width=True)
            diagnostics = result_50.get("failure_diagnostics", [])
            if diagnostics:
                st.warning("Failure diagnostics — no automatic retries in this diagnostic run.")
                st.dataframe(diagnostics, use_container_width=True)
        except Exception as exc:
            st.error(f"50-symbol parallel benchmark failed: {exc}")

