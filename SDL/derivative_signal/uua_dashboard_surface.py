from __future__ import annotations
from pathlib import Path
from datetime import date
from html import escape
from urllib.parse import urlencode
import gzip
import pickle
import pandas as pd
import streamlit as st
from uua_intelligence import UUAConfig, build_historical_change_comparison

STATE = Path(__file__).resolve().parent / "data" / "output" / "state"
REPLAY_CACHE_DIR = STATE / "replay_cache"


def _cache_path(trading_date: str) -> Path:
    return REPLAY_CACHE_DIR / f"{str(trading_date)[:10]}.pkl.gz"


def _read_cache(path: Path):
    if not path.is_file():
        return None
    try:
        with gzip.open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _cache_meta(trading_date: str) -> dict:
    path = _cache_path(trading_date)
    value = {"path": str(path), "exists": path.is_file(), "size": path.stat().st_size if path.is_file() else 0,
             "snapshots": 0, "pit_entries": 0, "first": "—", "last": "—", "complete": False}
    if not path.is_file():
        return value
    # Read only persisted cache metadata for truthful UI counters. This does
    # not build UUA results or mutate the cache.
    try:
        raw = _read_cache(path)
        if not isinstance(raw, dict):
            return value
        snapshots = raw.get("snapshots", {}) if isinstance(raw, dict) else {}
        logical = [(str(k), v) for k, v in snapshots.items()
                   if str(k).startswith("logical::") and isinstance(v, pd.DataFrame) and not v.empty]
        value["_uua_logical_count"] = len(logical)
        pit_map = raw.get("point_in_time_cache", {})
        value["_uua_pit_count"] = len(pit_map) if isinstance(pit_map, dict) else 0
        times = []
        for key, frame in logical:
            ts_col = next((c for c in ("source_timestamp", "observation_timestamp", "timestamp") if c in frame.columns), None)
            if ts_col:
                times.extend(pd.to_datetime(frame[ts_col], errors="coerce").dropna().tolist())
        if times:
            value["_uua_first_ts"] = min(times)
            value["_uua_last_ts"] = max(times)
    except Exception:
        pass
    return value


def _load_current_cache(trading_date: str) -> tuple[pd.DataFrame, dict]:
    raw = _read_cache(_cache_path(trading_date))
    if not isinstance(raw, dict):
        return pd.DataFrame(), {}
    frames = []
    snapshots = raw.get("snapshots", {})
    if isinstance(snapshots, dict):
        for key, frame in snapshots.items():
            if str(key).startswith("logical::") and isinstance(frame, pd.DataFrame) and not frame.empty:
                # Cached logical snapshots can carry pandas attrs containing
                # DataFrame/Series objects. pandas.concat compares attrs across
                # frames and that comparison raises "truth value of a DataFrame
                # is ambiguous". UUA does not depend on snapshot attrs, so strip
                # them before concatenation while preserving all columns/values.
                clean = frame.copy()
                clean.attrs = {}
                frames.append(clean)
    if not frames:
        return pd.DataFrame(), raw
    current = pd.concat(frames, ignore_index=True)
    current = current.loc[:, ~pd.Index(current.columns).duplicated(keep="first")].copy()
    return current, raw


def _load_history_caches(trading_date: str, max_days: int) -> dict:
    try:
        today = pd.Timestamp(trading_date).date()
    except Exception:
        return {}
    candidates = []
    for p in REPLAY_CACHE_DIR.glob("*.pkl.gz"):
        try:
            d = pd.Timestamp(p.name[:10]).date()
        except Exception:
            continue
        if d < today:
            candidates.append((d, p))
    out = {}
    for d, p in sorted(candidates, reverse=True)[: int(max_days)]:
        raw = _read_cache(p)
        if raw is not None:
            out[str(d)] = raw
    return out


def _scope(frame, queue):
    if not queue:
        return frame
    col = next((c for c in ("symbol", "Symbol", "ticker", "Ticker") if c in frame.columns), None)
    if col is None:
        return frame.iloc[0:0]
    wanted = {str(x).strip().upper() for x in queue if str(x).strip()}
    return frame.loc[frame[col].astype(str).str.strip().str.upper().isin(wanted)].copy()



def _sdl_flags(frame: pd.DataFrame, queue: list[str]) -> pd.Series:
    symbols = frame["symbol"].astype(str).str.upper() if "symbol" in frame.columns else pd.Series("", index=frame.index)
    wanted = {str(x).strip().upper() for x in queue if str(x).strip()}
    return symbols.isin(wanted)


def _ratio_text(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.2f}×"


def _value_text(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):+.2f}%"


def _grade_style(value):
    palette = {
        "STRONGEST": "background-color: #ff4b4b; color: #111; font-weight: 700",
        "VERY STRONG": "background-color: #ff8c42; color: #111; font-weight: 700",
        "STRONG": "background-color: #ffd166; color: #111; font-weight: 700",
        "ELEVATED": "background-color: #d9f99d; color: #111; font-weight: 700",
        "NORMAL": "background-color: #eef2f7; font-weight: 600",
    }
    return palette.get(str(value), "")


def _ratio_style_text(value):
    try:
        if value in (None, "—", "") or pd.isna(value):
            return ""
        x = float(str(value).replace("×", "").strip())
    except Exception:
        return ""
    if x >= 4:
        return "background-color: #ff4b4b; color: #111; font-weight: 700"
    if x >= 3:
        return "background-color: #ff8c42; color: #111; font-weight: 700"
    if x >= 2:
        return "background-color: #ffd166; color: #111; font-weight: 700"
    if x >= 1.5:
        return "background-color: #d9f99d; color: #111; font-weight: 700"
    return ""


def _direction_style(value):
    text = str(value).upper()
    if "BULL" in text or text == "LONG":
        return "color: #118a44; font-weight: 700"
    if "BEAR" in text or text == "SHORT":
        return "color: #d62728; font-weight: 700"
    return ""


def _build_display_table(result: pd.DataFrame, queue: list[str], selected_direction: str, selected_sdl: str) -> pd.DataFrame:
    if not isinstance(result, pd.DataFrame) or result.empty:
        return pd.DataFrame()
    x = result.copy()
    x["SDL"] = _sdl_flags(x, queue).map({True: "YES", False: "NO"})
    x["Direction"] = x.get("direction", pd.Series("", index=x.index)).astype(str).str.upper()
    x["Direction"] = x["Direction"].replace({"NAN": "", "NONE": ""})
    if selected_sdl != "ALL":
        x = x.loc[x["SDL"].eq(selected_sdl)].copy()
    if selected_direction != "ALL":
        wanted = selected_direction.upper()
        pattern = "BULL|LONG" if wanted == "BULLISH" else "BEAR|SHORT"
        x = x.loc[x["Direction"].str.contains(pattern, regex=True, na=False)].copy()
    if x.empty:
        return pd.DataFrame()

    metrics = ["FUTURES_OI_CHANGE_PCT", "CE_MINUS_PE_OI_CHANGE"]
    parts = []
    for metric in metrics:
        m = x.loc[x["metric_key"].eq(metric)].copy()
        if m.empty:
            continue
        m = m.set_index("symbol")
        keep = [c for c in ("current_value", "ratio_last", "ratio_3d_max", "ratio_5d_max", "ratio_10d_max", "ratio_20d_max", "grade") if c in m.columns]
        m = m[keep].copy()
        m.columns = [f"{c}__{metric}" for c in m.columns]
        parts.append(m)
    if not parts:
        return pd.DataFrame()
    piv = parts[0]
    for part in parts[1:]:
        piv = piv.join(part, how="outer")
    meta = x.drop_duplicates("symbol").set_index("symbol")[["SDL", "Direction"]]
    piv = piv.join(meta, how="left").reset_index()

    def strongest(a, b):
        order = {"NORMAL": 0, "ELEVATED": 1, "STRONG": 2, "VERY STRONG": 3, "STRONGEST": 4}
        vals = [str(v) for v in (a, b) if pd.notna(v)]
        return max(vals, key=lambda v: order.get(v, 0)) if vals else "NORMAL"
    ga = piv.get("grade__FUTURES_OI_CHANGE_PCT", pd.Series(index=piv.index, dtype=object))
    gb = piv.get("grade__CE_MINUS_PE_OI_CHANGE", pd.Series(index=piv.index, dtype=object))
    piv["Grade"] = [strongest(a, b) for a, b in zip(ga, gb)]

    rename = {
        "current_value__FUTURES_OI_CHANGE_PCT": "Futures OI Δ",
        "ratio_last__FUTURES_OI_CHANGE_PCT": "FUT × Last",
        "ratio_3d_max__FUTURES_OI_CHANGE_PCT": "FUT × 3D Max",
        "ratio_5d_max__FUTURES_OI_CHANGE_PCT": "FUT × 5D Max",
        "ratio_10d_max__FUTURES_OI_CHANGE_PCT": "FUT × 10D Max",
        "ratio_20d_max__FUTURES_OI_CHANGE_PCT": "FUT × 20D Max",
        "current_value__CE_MINUS_PE_OI_CHANGE": "CE−PE OI Δ",
        "ratio_last__CE_MINUS_PE_OI_CHANGE": "OPT × Last",
        "ratio_3d_max__CE_MINUS_PE_OI_CHANGE": "OPT × 3D Max",
        "ratio_5d_max__CE_MINUS_PE_OI_CHANGE": "OPT × 5D Max",
        "ratio_10d_max__CE_MINUS_PE_OI_CHANGE": "OPT × 10D Max",
        "ratio_20d_max__CE_MINUS_PE_OI_CHANGE": "OPT × 20D Max",
    }
    out = piv.rename(columns=rename)
    wanted_cols = [
        "symbol", "SDL", "Direction", "Grade", "Futures OI Δ", "FUT × Last", "FUT × 3D Max", "FUT × 5D Max", "FUT × 10D Max", "FUT × 20D Max",
        "CE−PE OI Δ", "OPT × Last", "OPT × 3D Max", "OPT × 5D Max", "OPT × 10D Max", "OPT × 20D Max",
    ]
    for col in wanted_cols:
        if col not in out:
            out[col] = None
    out = out[wanted_cols].rename(columns={"symbol": "Stock"})
    out["Futures OI Δ"] = out["Futures OI Δ"].map(_value_text)
    out["CE−PE OI Δ"] = out["CE−PE OI Δ"].map(_value_text)
    for col in [c for c in out.columns if "×" in c]:
        out[col] = out[col].map(_ratio_text)
    rank = {"STRONGEST": 4, "VERY STRONG": 3, "STRONG": 2, "ELEVATED": 1, "NORMAL": 0}
    out["__rank"] = out["Grade"].map(rank).fillna(0)
    return out.sort_values(["__rank", "Stock"], ascending=[False, True]).drop(columns="__rank")


def _render_historical_table(display: pd.DataFrame):
    if display.empty:
        st.info("No stocks meet the current SDL/direction/strength filters.")
        return
    style = display.style.map(_grade_style, subset=["Grade"])
    style = style.map(_direction_style, subset=["Direction"])
    for col in [c for c in display.columns if "×" in c]:
        style = style.map(_ratio_style_text, subset=[col])
    st.dataframe(style, use_container_width=True, hide_index=True, height=520)

def _download(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return
    out = frame.loc[:, ~pd.Index(frame.columns).duplicated(keep="first")].copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    st.download_button("Download UUA CSV", out.to_csv(index=False).encode("utf-8-sig"), file_name="uua_results.csv", mime="text/csv", use_container_width=True, key="uua_download_results_final")




def _load_live_current(trading_date: str) -> tuple[pd.DataFrame, dict]:
    state_path = STATE / 'processing_state.json'
    try:
        if state_path.is_file():
            import json
            payload = json.loads(state_path.read_text(encoding='utf-8'))
            root = payload.get('derivative_signal', {})
            day_state = root.get(str(trading_date)[:10], {}) if isinstance(root, dict) else {}
            durable = day_state.get('last_complete_state', {}) if isinstance(day_state, dict) else {}
            result = durable.get('result') if isinstance(durable, dict) else None
            if isinstance(result, list) and result:
                frame = pd.DataFrame(result)
                if not frame.empty:
                    return frame, durable
    except Exception:
        pass
    return _load_current_cache(trading_date)


def _uua_workspace():
    """Trader-facing Historical Derivative Activity workspace.

    LIVE and REPLAY use the same persisted logical snapshot cache. UUA reads
    evidence only; SDL qualification/ranking/scoring remains untouched.
    """
    trading_date = str(st.session_state.get("uua_runtime_trading_date", "")).strip()
    queue = list(st.session_state.get("uua_runtime_live_queue_symbols", []))
    meta = st.session_state.get("uua_cache_meta_final", {})
    st.markdown("## UUA • Historical Derivative Activity")
    st.caption("Actual CHANGE values only • Futures OI Change % + CE−PE OI Change • comparisons use prior EOD CHANGE values • SDL remains the decision owner")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        mode = st.radio("View", ["LIVE", "REPLAY"], horizontal=True, key="uua_view_v2")
    with c2:
        if mode == "LIVE":
            st.caption("LIVE: latest durable complete snapshot")
        else:
            st.caption("REPLAY: persisted point-in-time snapshot")
    with c3:
        st.caption("Replay is point-in-time. LIVE is sourced independently from the durable last-complete state.")

    if mode == "REPLAY":
        current, _raw = _load_current_cache(trading_date)
        source_caption = "Source: persisted replay/PIT cache"
        empty_message = f"No logical snapshots found in {_cache_path(trading_date)}"
    else:
        current, _raw = _load_live_current(trading_date)
        source_caption = "Source: durable last-complete LIVE state"
        empty_message = "No durable LIVE snapshot is available for UUA."

    st.caption(source_caption)
    if current.empty:
        st.error(empty_message)
        return

    prepared_ts = pd.to_datetime(current.get("_ts", pd.Series(dtype=object)), errors="coerce")
    if prepared_ts.empty or prepared_ts.dropna().empty:
        ts_col = next((c for c in ("source_timestamp", "observation_timestamp", "timestamp") if c in current.columns), None)
        prepared_ts = pd.to_datetime(current[ts_col], errors="coerce") if ts_col else pd.Series(dtype="datetime64[ns]")
    timestamps = sorted(pd.Series(prepared_ts.dropna().unique()).tolist())
    if not timestamps:
        st.error("No valid logical snapshot timestamps are available.")
        return

    if mode == "LIVE":
        selected_ts = pd.Timestamp(timestamps[-1])
        st.caption(f"LIVE point: {selected_ts:%H:%M:%S}")
    else:
        labels = {pd.Timestamp(t): pd.Timestamp(t).strftime("%H:%M:%S") for t in timestamps}
        selected_label = st.selectbox("Replay PIT time", list(labels.values()), index=len(labels)-1, key="uua_replay_time_v2")
        selected_ts = next(pd.Timestamp(t) for t, label in labels.items() if label == selected_label)

    f1, f2, f3 = st.columns(3)
    with f1:
        sdl_filter = st.radio("SDL", ["ALL", "YES", "NO"], horizontal=True, key="uua_sdl_filter_v2")
    with f2:
        direction_filter = st.radio("Direction", ["ALL", "BULLISH", "BEARISH"], horizontal=True, key="uua_direction_filter_v2")
    with f3:
        grade_filter = st.multiselect("Strength", ["STRONGEST", "VERY STRONG", "STRONG", "ELEVATED", "NORMAL"], default=[], key="uua_grade_filter_v2")

    hist = _load_history_caches(trading_date, 20)
    if not hist:
        st.warning("No prior trading-day replay caches are available. Today's actual change values can be shown, but historical multiples cannot yet be calculated.")

    cfg = UUAConfig(history_days=(3, 5, 10, 20))
    result = build_historical_change_comparison(
        current,
        hist,
        timestamp=selected_ts,
        config=cfg,
        scope="ALL TODAY",
    )
    if result.empty:
        st.warning("The selected snapshot does not contain the required Futures OI Change % and/or CE−PE OI Change fields.")
        st.caption("No PE OI or CE OI absolute balances are compared. UUA uses change values only.")
        return

    display = _build_display_table(result, queue, direction_filter, sdl_filter)
    if grade_filter:
        display = display.loc[display["Grade"].isin(grade_filter)].copy()

    st.markdown("### Historical comparison")
    st.caption("1D = previous trading-day EOD change. 3D/5D/10D/20D = maximum absolute CHANGE over prior completed sessions. Multiples use magnitude; the signed actual CHANGE remains visible.")
    _render_historical_table(display)

    # Compact selected-stock evidence detail with signed historical references.
    if not display.empty:
        selected_stock = st.selectbox("Stock detail", ["—"] + display["Stock"].tolist(), key="uua_stock_detail_v2")
        if selected_stock != "—":
            detail = result.loc[result["symbol"].eq(selected_stock)].copy()
            st.markdown(f"### {selected_stock} • change evidence")
            cols = ["metric", "current_value", "previous_eod_value", "max_3d_value", "max_5d_value", "max_10d_value", "max_20d_value", "ratio_last", "ratio_3d_max", "ratio_5d_max", "ratio_10d_max", "ratio_20d_max", "new_3d", "new_5d", "new_10d", "new_20d", "grade", "comparison_days"]
            st.dataframe(detail[cols], use_container_width=True, hide_index=True)

    st.download_button(
        "Download historical comparison CSV",
        result.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"uua_historical_change_{trading_date}_{selected_ts:%H%M%S}.csv",
        mime="text/csv",
        use_container_width=True,
        key="uua_download_historical_v2",
    )

def _query_value(name: str, default: str = "") -> str:
    try:
        value = st.query_params.get(name, default)
    except Exception:
        value = default
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default).strip()


def render_uua_surface(*, snapshot_results, snapshot_label, trading_date, live_queue_symbols=None):
    """Cheap launcher only. UUA data is never calculated on the main dashboard."""
    day = str(trading_date or st.session_state.get("ds_trading_date", "")).strip()
    symbols = [str(v).strip().upper() for v in (live_queue_symbols or []) if str(v).strip()]
    params = {"view": "uua"}
    if day:
        params["date"] = day
    if symbols:
        params["symbols"] = ",".join(dict.fromkeys(symbols))
    href = "?" + urlencode(params)
    st.markdown(
        f"""<div style="margin:8px 0 12px;padding:10px 12px;border:1px solid rgba(120,130,150,.28);border-radius:8px;">
<div style="font-weight:650;margin-bottom:5px">UUA • Unusual Activity Intelligence</div>
<div style="font-size:12px;opacity:.78;margin-bottom:8px">Independent evidence window. The default scope is the existing SDL-qualified population; SDL selection/ranking/scoring remains untouched.</div>
<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:7px 14px;border-radius:6px;background:#ff4b4b;color:white !important;text-decoration:none;font-weight:600">Open UUA in separate window</a>
<span style="font-size:11px;opacity:.65;margin-left:9px">same 8505 • no second port</span>
</div>""",
        unsafe_allow_html=True,
    )


def render_uua_fullscreen() -> None:
    """Render UUA as a dedicated same-8505 query route."""
    day = _query_value("date", "") or date.today().strftime("%Y-%m-%d")
    raw_symbols = _query_value("symbols", "")
    queue = [x.strip().upper() for x in raw_symbols.split(",") if x.strip()]
    st.set_page_config(page_title="NTIS SDL — UUA Intelligence", layout="wide")
    st.markdown(
        """<style>
        .uua-title {font-size:28px;font-weight:700;margin-bottom:2px}
        .uua-sub {opacity:.72;margin-bottom:12px}
        </style>""", unsafe_allow_html=True
    )
    st.markdown('<div class="uua-title">UUA • Unusual Activity Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="uua-sub">Dedicated same-8505 workspace • cache-native • evidence-only • SDL remains the decision owner.</div>',
        unsafe_allow_html=True,
    )
    path = _cache_path(day)
    meta = {"exists": path.is_file(), "snapshots": "—", "pit_entries": "—", "last": "—"}
    if path.is_file():
        meta["last"] = "available in cache"
    st.session_state["uua_runtime_trading_date"] = day
    st.session_state["uua_runtime_live_queue_symbols"] = queue
    st.session_state["uua_cache_meta_final"] = meta
    _uua_workspace()
