from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import gzip
import pickle
from urllib.parse import parse_qs

import pandas as pd
import streamlit as st

from uua_intelligence import (
    UUAConfig,
    UUA_COLUMNS,
    _metric_columns,
    _prepare,
    _num,
    build_pit_uua,
    build_day_start_uua,
    build_same_time_uua,
    build_eod_uua,
)

BASE = Path(__file__).resolve().parent
CACHE_ROOT = BASE / "data" / "output" / "state" / "replay_cache"


def _load_cache(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rb") as fh:
            obj = pickle.load(fh)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def cache_dates() -> list[str]:
    dates = []
    for p in CACHE_ROOT.glob("*.pkl.gz"):
        try:
            dates.append(str(pd.Timestamp(p.stem.replace(".pkl", "")).date()))
        except Exception:
            pass
    return sorted(set(dates), reverse=True)


def flatten_cache(cache: Mapping[str, Any] | None, day: str) -> pd.DataFrame:
    """Use only logical snapshot DataFrames; never concatenate timeline/PIT metadata."""
    if not isinstance(cache, Mapping):
        return pd.DataFrame()
    snaps = cache.get("snapshots")
    if not isinstance(snaps, Mapping):
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for key, value in snaps.items():
        if not isinstance(value, pd.DataFrame) or value.empty:
            continue
        f = value.copy()
        if "trading_date" not in f.columns:
            f["trading_date"] = day
        f["__uua_snapshot_key"] = str(key)
        frames.append(f)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    keep = ~pd.Index(merged.columns).duplicated(keep="first")
    merged = merged.loc[:, keep].copy()
    sym = next((c for c in ("symbol", "Symbol", "ticker", "Ticker") if c in merged.columns), None)
    ts = next((c for c in ("source_timestamp", "observation_timestamp", "timestamp") if c in merged.columns), None)
    if sym and ts:
        merged["__uua_sym"] = merged[sym].astype(str).str.strip().str.upper()
        merged["__uua_ts"] = pd.to_datetime(merged[ts], errors="coerce")
        merged = merged.sort_values(["__uua_ts", "__uua_sym", "__uua_snapshot_key"])
        merged = merged.drop_duplicates(["__uua_ts", "__uua_sym"], keep="first")
        merged = merged.drop(columns=["__uua_sym", "__uua_ts", "__uua_snapshot_key"], errors="ignore")
    else:
        merged = merged.drop(columns=["__uua_snapshot_key"], errors="ignore")
    return merged.reset_index(drop=True)


def load_day(day: str) -> tuple[dict[str, Any], pd.DataFrame]:
    path = CACHE_ROOT / f"{day}.pkl.gz"
    cache = _load_cache(path) if path.exists() else {}
    return cache, flatten_cache(cache, day)


def load_prior_caches(day: str, max_days: int) -> dict[str, dict[str, Any]]:
    try:
        current = pd.Timestamp(day).date()
    except Exception:
        return {}
    candidates = []
    for p in CACHE_ROOT.glob("*.pkl.gz"):
        try:
            d = pd.Timestamp(p.stem.replace(".pkl", "")).date()
        except Exception:
            continue
        if d < current:
            candidates.append((d, p))
    candidates.sort(reverse=True)
    return {str(d): _load_cache(p) for d, p in candidates[:max(1, int(max_days))]}


def metric_catalog(frame: pd.DataFrame) -> dict[str, str]:
    raw = _metric_columns(frame)
    return {str(k): str(v) for k, v in raw.items() if v}


def post_filter(result: pd.DataFrame, *, event: str, threshold: float, direction: str,
                unusual_only: bool, z_threshold: float, ratio_threshold: float,
                min_abs: float, min_baseline: float, min_samples: int,
                multi_metric: bool) -> pd.DataFrame:
    if not isinstance(result, pd.DataFrame) or result.empty:
        return pd.DataFrame(columns=UUA_COLUMNS)
    out = result.copy()
    if min_samples:
        out = out[pd.to_numeric(out["comparison_count"], errors="coerce") >= min_samples]
    if min_abs:
        out = out[pd.to_numeric(out["current_magnitude"], errors="coerce") >= min_abs]
    if min_baseline:
        out = out[pd.to_numeric(out["baseline_median"], errors="coerce").abs() >= min_baseline]
    if direction != "ALL":
        vals = pd.to_numeric(out["current_value"], errors="coerce")
        out = out[(vals > 0) if direction == "BULLISH" else (vals < 0)]
    ratio = pd.to_numeric(out["ratio"], errors="coerce")
    z = pd.to_numeric(out["robust_z"], errors="coerce")
    if event == "EXPANSION":
        out = out[ratio >= threshold]
    elif event == "CONTRACTION":
        out = out[ratio.notna() & (ratio <= 1.0 / max(threshold, 1e-9))]
    if unusual_only:
        out = out[(ratio >= ratio_threshold) | (z >= z_threshold)]
    if multi_metric and not out.empty:
        counts = out.groupby("symbol")["event"].nunique()
        out = out[out["symbol"].isin(counts[counts >= 2].index)]
    return out.sort_values(["unusual", "robust_z", "ratio"], ascending=[False, False, False], na_position="last").reset_index(drop=True)


def render_table(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.info("No UUA observations satisfy the selected filters.")
        return
    show = frame.copy()
    if "current_timestamp" in show.columns:
        show["current_timestamp"] = pd.to_datetime(show["current_timestamp"], errors="coerce").dt.strftime("%H:%M:%S")
    for c in ("current_value", "current_magnitude", "absolute_change", "pct_change", "baseline_median", "ratio", "robust_z"):
        if c in show.columns:
            show[c] = pd.to_numeric(show[c], errors="coerce").round(3)
    show = show.rename(columns={
        "symbol":"Stock", "event":"Metric", "event_type":"Event", "current_timestamp":"Time",
        "current_value":"Current", "absolute_change":"Δ", "pct_change":"Δ%",
        "baseline_median":"Baseline", "ratio":"×", "robust_z":"Z",
        "comparison_count":"N", "comparison_window":"Reference", "unusual":"UUA",
    })
    cols = [c for c in ["Stock","Metric","Event","Time","Current","Δ","Δ%","Baseline","×","Z","N","Reference","UUA"] if c in show.columns]
    st.dataframe(show[cols].head(300), use_container_width=True, hide_index=True, height=560)


def main() -> None:
    st.set_page_config(page_title="NTIS UUA Intelligence", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")
    st.title("🔎 UUA • Unusual Activity Intelligence")
    st.caption("Independent evidence window • replay-cache native • SDL remains the decision owner")

    dates = cache_dates()
    if not dates:
        st.error(f"No replay cache found under {CACHE_ROOT}")
        st.stop()

    query_date = str(st.query_params.get("date", "")).strip()
    default_day = query_date if query_date in dates else dates[0]
    day = st.selectbox("Trading date", dates, index=dates.index(default_day))
    cache, current = load_day(day)
    if current.empty:
        st.error("Selected cache contains no usable logical snapshot DataFrames.")
        st.stop()

    latest = _prepare(current)
    latest_ts = latest["_ts"].max() if not latest.empty else pd.NaT
    catalog = metric_catalog(current)
    supported = list(catalog)

    p_symbols = str(st.query_params.get("symbols", ""))
    queue_symbols = {x.strip().upper() for x in p_symbols.split(",") if x.strip()}

    a, b, c = st.columns([1.2, 1.2, 3.0])
    with a:
        scope = st.selectbox("Scope", ["AVAILABLE CHRONOLOGICAL UNIVERSE", "LIVE QUEUE"])
    with b:
        mode = st.selectbox("Comparison mode", ["PIT", "DAY START / CUMULATIVE", "SAME-TIME", "EOD"])
    with c:
        st.info(f"Cache {day} • latest {latest_ts:%H:%M:%S} • logical snapshots {len(cache.get('snapshots', {}))}")

    if scope == "LIVE QUEUE":
        if queue_symbols:
            sym_col = next((x for x in ("symbol","Symbol","ticker","Ticker") if x in current.columns), None)
            if sym_col:
                current = current[current[sym_col].astype(str).str.strip().str.upper().isin(queue_symbols)].copy()
        else:
            st.warning("No LIVE Queue symbols were passed from 8505; using the available chronological universe.")

    st.subheader("Metrics — complete source-capability catalogue")
    groups = {
        "OI / Position": ["CE_OI_CHANGE","PE_OI_CHANGE","PE_MINUS_CE_OI","FUTURES_OI_CHANGE","PCR"],
        "Activity": ["VOLUME"],
        "Price / Volatility": ["PRICE","IV"],
    }
    selected: list[str] = []
    cc = st.columns(3)
    for i, (label, names) in enumerate(groups.items()):
        options = [x for x in names if x in supported]
        with cc[i]:
            selected.extend(st.multiselect(label, options, default=[], key=f"uua_select_{i}"))
    with st.expander("Additional supported metrics", expanded=False):
        extras = [x for x in supported if x not in selected]
        selected.extend(st.multiselect("Additional", extras, default=[], key="uua_extra"))

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        threshold = st.selectbox("Threshold", [1.5,2.0,2.5,3.0,5.0], index=1, format_func=lambda x:f"{x:g}×")
    with r2:
        event = st.selectbox("Event", ["EXPANSION","CONTRACTION","ALL"])
    with r3:
        pit_window = st.selectbox("PIT window", [15,30,60,120,240], index=0, format_func=lambda x:f"{x}M", disabled=mode != "PIT")
    with r4:
        historical_days = st.selectbox("Historical days", [5,10,20], index=1)

    st.subheader("Advanced filters")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        min_abs = st.number_input("Minimum absolute change", min_value=0.0, value=0.0, step=0.1)
        direction = st.selectbox("Direction", ["ALL","BULLISH","BEARISH"])
    with q2:
        min_samples = st.number_input("Minimum historical samples", min_value=1, value=3, step=1)
    with q3:
        min_baseline = st.number_input("Minimum baseline", min_value=0.0, value=0.0, step=0.1)
        z_threshold = st.number_input("Historical Z threshold", min_value=0.1, value=2.0, step=0.1)
    with q4:
        tolerance = st.number_input("Same-time tolerance (minutes)", min_value=0, value=7, step=1)
        ratio_threshold = st.number_input("Historical ratio threshold", min_value=0.1, value=2.0, step=0.1)

    unusual_only = st.checkbox("Unusual only", value=True)
    multi_metric = st.checkbox("Multi-metric confirmation (≥2)", value=False)

    x1, x2, x3 = st.columns([2,1,1])
    with x1:
        calculate = st.button("Apply / Recalculate UUA", type="primary", use_container_width=True)
    with x2:
        restore = st.button("Restore all metrics", use_container_width=True)
    with x3:
        clear = st.button("Clear result", use_container_width=True)

    if restore:
        for i, names in enumerate(groups.values()):
            st.session_state[f"uua_select_{i}"] = [x for x in names if x in supported]
        st.rerun()
    if clear:
        st.session_state.pop("uua_result", None)
        st.rerun()

    if calculate:
        if not selected:
            st.warning("Select at least one supported metric.")
        else:
            cfg = UUAConfig(
                pit_windows=(int(pit_window),),
                eod_days=(1,3,5,10,20),
                historical_days=(5,10,20),
                ratio_threshold=float(ratio_threshold),
                robust_z_threshold=float(z_threshold),
                same_time_tolerance_minutes=int(tolerance),
                min_absolute_change=float(min_abs),
                min_baseline=float(min_baseline),
                min_samples=int(min_samples),
            )
            # The intelligence engine emits all source-capable metrics. Restrict
            # after computation to exactly the user-selected metrics; no missing
            # PE/CE fields are invented.
            if mode == "PIT":
                raw = build_pit_uua(current, timestamp=None, config=cfg, scope=scope)
            else:
                prior = load_prior_caches(day, historical_days)
                if mode == "DAY START / CUMULATIVE":
                    raw = build_day_start_uua(current, prior, timestamp=None, config=cfg, scope=scope)
                elif mode == "SAME-TIME":
                    raw = build_same_time_uua(current, prior, timestamp=None, days=historical_days, config=cfg, scope=scope)
                else:
                    raw = build_eod_uua(current, prior, timestamp=None, config=cfg, scope=scope)
            if not raw.empty:
                raw = raw[raw["event"].isin(selected)].copy()
            st.session_state["uua_result"] = post_filter(
                raw, event=event, threshold=float(threshold), direction=direction,
                unusual_only=unusual_only, z_threshold=float(z_threshold),
                ratio_threshold=ratio_threshold, min_abs=min_abs,
                min_baseline=min_baseline, min_samples=min_samples,
                multi_metric=multi_metric,
            )

    result = st.session_state.get("uua_result")
    if isinstance(result, pd.DataFrame):
        st.divider()
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("UUA rows", len(result))
        m2.metric("Stocks", int(result["symbol"].nunique()) if "symbol" in result else 0)
        m3.metric("Latest", str(pd.to_datetime(result["current_timestamp"], errors="coerce").max().strftime("%H:%M:%S")) if not result.empty else "—")
        m4.metric("Cache snapshots", len(cache.get("snapshots", {})))
        render_table(result)

    st.caption("UUA is evidence-only. It cannot add, remove, re-rank, or re-score SDL candidates.")


if __name__ == "__main__":
    main()
