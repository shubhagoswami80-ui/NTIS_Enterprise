
from __future__ import annotations
from pathlib import Path
import argparse, json, re, itertools, math
import numpy as np
import pandas as pd

IST = "Asia/Kolkata"

def norm(x):
    return re.sub(r"\s+", " ", str(x).lower().replace("_", " ")).strip()

def numeric(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False)
         .str.replace("−", "-", regex=False)
         .str.replace("%", "", regex=False),
        errors="coerce"
    )

def exact(cols, aliases):
    mp = {norm(c): c for c in cols}
    for a in aliases:
        if norm(a) in mp:
            return mp[norm(a)]
    return None

def source_timestamp(path):
    """Resolve the report/session timestamp from the filename/path first.

    The raw repository contains report-generated timestamps in names such as
    ``...Report_4_9_2026_144321.xlsx``.  Filesystem creation time is only a
    fallback because copy/extraction time is not the market observation time.
    Date-only report names retain the filesystem clock but replace its date
    with the authoritative report date.
    """
    name = path.name
    # Explicit timestamp: DD_M_YYYY_HHMMSS / D_M_YYYY_HHMMSS
    m = re.search(r"(?:^|[_-])(\d{1,2})[_-](\d{1,2})[_-](\d{4})[_-](\d{6})(?:\D|$)", name)
    if m:
        d, mo, y, hms = m.groups()
        try:
            return pd.to_datetime(f"{y}-{int(mo):02d}-{int(d):02d} {hms}")
        except Exception:
            pass
    # ISO date in filename/path, with optional adjacent HHMMSS.
    # This must be checked before the date-only fallback because many raw
    # reports use names such as ...2026-09-04_144321.xlsx.
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})[T _-](\d{6})(?:\D|$)", name)
    if m:
        y, mo, d, hms = m.groups()
        try:
            return pd.to_datetime(f"{y}-{mo}-{d} {hms}")
        except Exception:
            pass
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", name)
    if not m:
        for part in path.parts:
            m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", str(part))
            if m:
                break
    if m:
        y, mo, d = m.groups()
        try:
            try:
                base = pd.Timestamp.fromtimestamp(path.stat().st_ctime, tz=IST).tz_localize(None)
                hh, mm, ss, us = base.hour, base.minute, base.second, base.microsecond
            except Exception:
                hh = mm = ss = us = 0
            return pd.Timestamp(year=int(y), month=int(mo), day=int(d),
                                hour=hh, minute=mm, second=ss, microsecond=us)
        except Exception:
            pass
    # Compact date/time occasionally used by report generators.
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[_-](\d{6})", name)
    if m:
        y, mo, d, hms = m.groups()
        try:
            return pd.to_datetime(f"{y}{mo}{d} {hms}", format="%Y%m%d %H%M%S")
        except Exception:
            pass
    try:
        return pd.Timestamp.fromtimestamp(path.stat().st_ctime, tz=IST).tz_localize(None)
    except Exception:
        return pd.NaT


# Backward-compatible name used by older code paths.
def ctime(path):
    return source_timestamp(path)

def row_timestamp(df, path, fallback):
    """Resolve per-row observation time when the workbook provides it.
    Priority: explicit datetime/timestamp column; date+time columns; filename/path timestamp;
    filesystem-derived fallback only when no authoritative timestamp exists.
    """
    cols = list(df.columns)
    def pick(aliases): return exact(cols, aliases)
    dt_col = pick(["Timestamp", "Time Stamp", "DateTime", "Date Time", "Observation Timestamp", "Report Timestamp", "Report Time"])
    if dt_col is not None:
        raw = df[dt_col].astype(str).str.strip()
        # Time-only values must be combined with the authoritative report/session date;
        # pandas otherwise attaches today's date, which would corrupt replay chronology.
        time_only = raw.str.fullmatch(r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?")
        if time_only.any() and pd.notna(fallback):
            tv = pd.to_datetime(raw.where(time_only), errors="coerce")
            base = pd.Timestamp(fallback).normalize()
            v = base + pd.to_timedelta(tv.dt.hour, unit="h") + pd.to_timedelta(tv.dt.minute, unit="m") + pd.to_timedelta(tv.dt.second, unit="s") + pd.to_timedelta(tv.dt.microsecond, unit="us")
            return v, "workbook_time_with_report_date"
        v = pd.to_datetime(df[dt_col], errors="coerce", dayfirst=False)
        if v.notna().any(): return v, "workbook_datetime"
    date_col = pick(["Date", "Trade Date", "Trading Date", "Report Date", "Observation Date"])
    time_col = pick(["Time", "Observation Time", "Observation Timestamp"])
    if date_col is not None and time_col is not None and date_col != time_col:
        v = pd.to_datetime(df[date_col].astype(str).str.strip()+" "+df[time_col].astype(str).str.strip(), errors="coerce")
        if v.notna().any(): return v, "workbook_date_time"
    # A time-only column can be anchored to the authoritative session date from filename/path.
    if time_col is not None:
        tv = pd.to_datetime(df[time_col].astype(str).str.strip(), errors="coerce")
        if tv.notna().any() and pd.notna(fallback):
            base = pd.Timestamp(fallback).normalize()
            v = base + pd.to_timedelta(tv.dt.hour, unit="h") + pd.to_timedelta(tv.dt.minute, unit="m") + pd.to_timedelta(tv.dt.second, unit="s")
            return v, "workbook_time_with_report_date"
    return pd.Series([fallback]*len(df), index=df.index), "report_or_filesystem_fallback"

def source_family(path):
    n = path.name.lower().replace(" ", "_")
    if "futuresoi" in n or "future_oi" in n or "futures_oi" in n:
        return "FUTURES"
    if "support" in n:
        return "SUPPORT"
    if "resistance" in n:
        return "RESISTANCE"
    if "sector_summary" in n or "sectorsummary" in n:
        return "SECTOR"
    if "ivr" in n:
        return "IVR"
    if "ivp" in n:
        return "IVP"
    if "pcr" in n:
        return "PCR"
    if "volumeandoispikes" in n or "volume" in n or "spike" in n:
        return "VOLUME"
    # The primary Daywise Price/OI workbook carries price, IV change,
    # option OI, PCR and related fields in the same file.
    if "daywise_price_and_oi" in n or "daywise" in n or "option" in n:
        return "OPTIONS"
    if "breakout" in n:
        return "BREAKOUT"
    return "OTHER"

def role_col(cols, aliases=(), contains=()):
    c = exact(cols, aliases)
    if c is not None:
        return c
    for col in cols:
        n = norm(col)
        if any(token in n for token in contains):
            return col
    return None

def parse_state(value):
    m = re.search(r"\b(LB|SB|SC)\b", str(value).upper())
    return m.group(1) if m else ""

def read_file(path):
    fam = source_family(path)
    if fam == "OTHER":
        return []
    try:
        xl = pd.ExcelFile(path)
    except Exception:
        return []

    rows = []
    ts = ctime(path)
    for sh in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sh)
        except Exception:
            continue
        if df.empty:
            continue

        cols = list(df.columns)
        sym = exact(cols, ["Symbol"])
        if not sym:
            continue

        # Exact role matching is intentional: do not let "Chg" match "Chg %".
        m = {
            "open": exact(cols, ["Open"]),
            "high": exact(cols, ["High"]),
            "low": exact(cols, ["Low"]),
            "close": exact(cols, ["Close"]),
            "price_chg": exact(cols, ["Price Chg", "Price chg"]),
            "price_chg_pct": exact(cols, ["Price Chg%", "Price chg (%)", "Price Chg %"]),
            "volume_pct": exact(cols, ["Volume Chg (%)", "Volume chg (%)"]),
            "ce_num": exact(cols, ["Tol CE OI Chg", "Tot CE OI Chg"]),
            "pe_num": exact(cols, ["Tol PE OI Chg", "Tot PE OI Chg"]),
            "pec_num": exact(cols, ["Tol PE-CE OI Chg", "Tot PE-CE OI Chg"]),
            "ce_pct": exact(cols, ["Tol CE OI Chg %", "Tot CE OI Chg %"]),
            "pe_pct": exact(cols, ["Tol PE OI Chg %", "Tot PE OI Chg %"]),
            "pec_pct": exact(cols, ["Tol PE-CE OI Chg %", "Tot PE-CE OI Chg %"]),
            "fut_num": exact(cols, ["OI Chg"]) if fam == "FUTURES" else None,
            "fut_pct": exact(cols, ["OI Chg %"]) if fam == "FUTURES" else None,
            "fut_state": exact(cols, ["Fut Buildup", "Buildup"]),
            "iv_chg": exact(cols, ["IV Chg", "IV chg"]),
            "iv_chg_pct": exact(cols, ["IV Chg %", "IV chg (%)", "IV Chg %"]),
            "pcr_chg": exact(cols, ["PCR Chg", "PCR chg"]),
            "pcr_chg_pct": exact(cols, ["PCR Chg %", "PCR chg (%)"]),
            "rollover": exact(cols, ["Rollover (%)", "Rollover %", "Rollover"]),
        }
        # Support/Resistance reports are identified by filename. Their level
        # column names vary, so resolve named role columns without requiring
        # one universal workbook schema. If a dedicated report has only a
        # generic Level/Price/Value column, use that as the role value.
        m["support_value"] = role_col(cols, ["Support", "Support Price", "Support Level", "S1"],
                                       ("support", "support level")) if fam == "SUPPORT" else None
        m["resistance_value"] = role_col(cols, ["Resistance", "Resistance Price", "Resistance Level", "R1"],
                                          ("resistance", "resistance level")) if fam == "RESISTANCE" else None
        if fam == "SUPPORT" and m["support_value"] is None:
            m["support_value"] = role_col(cols, contains=("level", "value", "price"))
        if fam == "RESISTANCE" and m["resistance_value"] is None:
            m["resistance_value"] = role_col(cols, contains=("level", "value", "price"))

        z = pd.DataFrame({"symbol": df[sym].astype(str).str.strip()})
        z["source_family"] = fam
        for k, col in m.items():
            z[k] = df[col] if col is not None else np.nan

        for k in [
            "open","high","low","close","price_chg","price_chg_pct","volume_pct",
            "ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct",
            "iv_chg","iv_chg_pct","pcr_chg","pcr_chg_pct","rollover","support_value","resistance_value"
        ]:
            z[k] = numeric(z[k])

        z["fut_state"] = z["fut_state"].map(parse_state)
        row_ts, ts_source = row_timestamp(df, path, ts)
        z["timestamp"] = row_ts.to_numpy()
        z["timestamp_source"] = ts_source
        z["source_file"] = str(path)
        z["source_name"] = path.name
        z["sheet"] = str(sh)
        z["family"] = fam
        rows.append(z)

    return rows

def magnitude_band(x):
    a = abs(x)
    if pd.isna(a): return ""
    if a > 1000: return ">1000"
    if a > 500: return "501-1000"
    return ""

def direction(x):
    if pd.isna(x) or x == 0: return "FLAT"
    return "UP" if x > 0 else "DOWN"

def option_direction(row):
    vals = []
    for k in ("ce_num","pe_num","pec_num"):
        if pd.notna(row[k]):
            vals.append(row[k])
    if not vals:
        return ""
    # Direction is intentionally not inferred from CE/PE alone.
    # PE-CE is the only directly directional option field; CE/PE are evidence components.
    if pd.notna(row["pec_num"]) and row["pec_num"] != 0:
        return "UP" if row["pec_num"] > 0 else "DOWN"
    return ""

def feature_flags(r):
    d = {}
    for k in ("ce_num","pe_num","pec_num"):
        v = r[k]
        d[k+"_500"] = pd.notna(v) and abs(v) > 500
        d[k+"_1000"] = pd.notna(v) and abs(v) > 1000
        d[k+"_pos500"] = pd.notna(v) and v > 500
        d[k+"_neg500"] = pd.notna(v) and v < -500
        d[k+"_pos1000"] = pd.notna(v) and v > 1000
        d[k+"_neg1000"] = pd.notna(v) and v < -1000

    v = r["fut_num"]
    d["fut_oi_500"] = pd.notna(v) and abs(v) > 500
    d["fut_oi_1000"] = pd.notna(v) and abs(v) > 1000
    d["fut_oi_pos500"] = pd.notna(v) and v > 500
    d["fut_oi_neg500"] = pd.notna(v) and v < -500
    d["fut_oi_pos1000"] = pd.notna(v) and v > 1000
    d["fut_oi_neg1000"] = pd.notna(v) and v < -1000

    p = r["fut_pct"]
    d["fut_pct_pos1"] = pd.notna(p) and p > 1
    d["fut_pct_neg1"] = pd.notna(p) and p < -1
    d["fut_pct_pos2"] = pd.notna(p) and p > 2
    d["fut_pct_neg2"] = pd.notna(p) and p < -2

    return d

def build_strength(df):
    # Volume is distribution-derived, never an arbitrary fixed final threshold.
    vol = df["volume_pct"].dropna().abs()
    qs = vol.quantile([.50,.75,.90,.95]).to_dict() if len(vol) else {}
    q50, q75, q90, q95 = [qs.get(q, np.nan) for q in (.50,.75,.90,.95)]

    def vband(x):
        if pd.isna(x): return ""
        a = abs(x)
        if pd.notna(q95) and a >= q95: return "V95"
        if pd.notna(q90) and a >= q90: return "V90"
        if pd.notna(q75) and a >= q75: return "V75"
        if pd.notna(q50) and a >= q50: return "V50"
        return "V<50"

    df["volume_band"] = df["volume_pct"].map(vband)
    df["price_direction"] = df["price_chg"].map(direction)

    for c in ("ce_num","pe_num","pec_num","fut_num","fut_pct","volume_pct"):
        df[c+"_present"] = df[c].notna()

    df["option_complete"] = df[["ce_num","pe_num","pec_num"]].notna().sum(axis=1)
    df["futures_complete"] = df[["fut_num","fut_pct","fut_state"]].replace("", np.nan).notna().sum(axis=1)
    df["core_evidence_count"] = (
        df[["price_chg","volume_pct","ce_num","pe_num","pec_num","fut_num","fut_pct"]]
        .notna().sum(axis=1)
    )

    # Strength is evidence completeness + magnitude + directional agreement + persistence.
    # It is a filtration bucket, not a predictive probability or score.
    df["magnitude_count"] = 0
    for c in ("ce_num","pe_num","pec_num"):
        df["magnitude_count"] += df[c].abs().gt(500).fillna(False).astype(int)
    df["magnitude_count"] += df["fut_num"].abs().gt(500).fillna(False).astype(int)
    df["magnitude_count"] += df["fut_pct"].abs().gt(1).fillna(False).astype(int)
    df["magnitude_count"] += df["volume_band"].isin(["V75","V90","V95"]).astype(int)

    # Evidence direction candidates. Futures direction requires state + price direction;
    # magnitude alone never creates LB/SB/SC.
    def fut_dir(row):
        # Futures direction is valid only when the explicit buildup state and
        # futures price direction agree. State alone is not directional evidence.
        state, pdirection = row["fut_state"], row["price_direction"]
        if state == "LB" and pdirection == "UP": return "UP"
        if state in ("SB", "SC") and pdirection == "DOWN": return "DOWN"
        return ""

    df["fut_direction"] = df.apply(fut_dir, axis=1)
    df["option_direction"] = df.apply(option_direction, axis=1)

    def agreement(row):
        dirs = [x for x in (row["price_direction"], row["option_direction"], row["fut_direction"]) if x in ("UP","DOWN")]
        if not dirs: return "NONE"
        return "AGREE" if len(set(dirs)) == 1 else ("MIXED" if len(set(dirs)) > 1 else "PARTIAL")
    df["direction_agreement"] = df.apply(agreement, axis=1)

    df = df.sort_values(["symbol","timestamp","family","source_file","sheet"]).reset_index(drop=True)
    # Same-family duplicate rows at the same source time are collapsed for strength/persistence.
    key = ["symbol","timestamp","family"]
    df["repeat_signature"] = (
        df[["price_direction","option_direction","fut_direction","volume_band"]]
        .fillna("").astype(str).agg("|".join, axis=1)
    )
    # Persistence = repeated aligned evidence across consecutive distinct source times.
    df["persistent"] = False
    prev = df.groupby("symbol")["repeat_signature"].shift(1)
    prev_ts = df.groupby("symbol")["timestamp"].shift(1)
    df.loc[(df["repeat_signature"] != "") & (df["repeat_signature"] == prev) &
           ((df["timestamp"] - prev_ts).dt.total_seconds().between(1, 900, inclusive="both")), "persistent"] = True

    df["strength_bucket"] = np.select(
        [
            (df["core_evidence_count"] >= 5) & (df["magnitude_count"] >= 3) &
            (df["direction_agreement"] == "AGREE") & df["persistent"],
            (df["core_evidence_count"] >= 4) & (df["magnitude_count"] >= 2) &
            (df["direction_agreement"] == "AGREE"),
            (df["core_evidence_count"] >= 3) & (df["magnitude_count"] >= 1),
        ],
        ["VERY_STRONG","STRONG","MODERATE"],
        default="WEAK"
    )
    return df, {"volume_abs_quantiles": {str(k): float(v) for k,v in qs.items()}}

def canonical_symbol(value):
    """Conservative cross-report symbol key for replay joins.

    Report families may render the same NSE symbol with harmless spacing/case
    differences or an EQ suffix. Do not strip other characters because those
    can change the instrument identity.
    """
    if pd.isna(value):
        return ""
    x = str(value).strip().upper()
    x = re.sub(r"\s+", "", x)
    if x.endswith("-EQ"):
        x = x[:-3]
    elif x.endswith(".EQ"):
        x = x[:-3]
    return x


def dedup_timeline(df):
    """Build the outcome PRICE stream only.

    Evidence-only rows are not allowed to become future price observations.
    A row qualifies for the price stream when it has at least one usable price
    level (OHLC/Close) or a price-change observation. Same symbol/day/timestamp
    rows are deduplicated with the strongest OHLC row retained.
    """
    x = df.copy()
    x["symbol_key"] = x["symbol"].map(canonical_symbol)
    x["trade_date"] = pd.to_datetime(x["timestamp"], errors="coerce").dt.date.astype(str)
    x = x.dropna(subset=["timestamp"]).copy()
    price_cols = ["open", "high", "low", "close", "price_chg"]
    x["_price_fields"] = x[price_cols].notna().sum(axis=1)
    x = x[x["_price_fields"] > 0].copy()
    if x.empty:
        return x
    x["price_quality"] = (
        x[["open","high","low","close"]].notna().sum(axis=1) * 10 +
        x["close"].notna().astype(int) * 2 +
        x["price_chg"].notna().astype(int)
    )
    x = x.sort_values(["symbol_key","trade_date","timestamp","price_quality","source_file"],
                      ascending=[True,True,True,False,True])
    x = x.drop_duplicates(["symbol_key","trade_date","timestamp"], keep="first")
    return x


def build_timeline_index(timeline):
    """Build a forward-replay index from the dedicated PRICE stream."""
    groups = {}
    if timeline.empty:
        return groups
    for key, g in timeline.groupby(["symbol_key", "trade_date"], sort=False):
        g = g.sort_values("timestamp")
        ts = pd.to_datetime(g["timestamp"], errors="coerce").astype("int64").to_numpy()
        close = pd.to_numeric(g["close"], errors="coerce").to_numpy(dtype=float)
        high = pd.to_numeric(g["high"], errors="coerce").to_numpy(dtype=float)
        low = pd.to_numeric(g["low"], errors="coerce").to_numpy(dtype=float)
        pchg = pd.to_numeric(g["price_chg"], errors="coerce").to_numpy(dtype=float)
        groups[key] = (ts, close, high, low, pchg)
    return groups


def evaluate_anchor_fast(symbol, day, ts_value, base, direction, timeline_index):
    """Forward-only replay: evidence freezes at T; only later PRICE rows count."""
    key = (canonical_symbol(symbol), str(day))
    item = timeline_index.get(key)
    if item is None:
        return ("NO_FOLLOW_UP", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    ts_ns, close, high, low, pchg = item
    anchor_ns = int(ts_value)

    # Latest usable accumulated price state at or before the anchor.
    state_pos = int(np.searchsorted(ts_ns, anchor_ns, side="right")) - 1
    while state_pos >= 0 and not np.isfinite(close[state_pos]):
        state_pos -= 1
    if state_pos < 0:
        return ("UNKNOWN_DIRECTION", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    state_close = float(close[state_pos])
    base = state_close if np.isfinite(state_close) else base
    if not np.isfinite(float(base)):
        return ("UNKNOWN_DIRECTION", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    state_direction = direction if direction in ("UP","DOWN") else None
    if state_direction is None:
        for j in range(state_pos, -1, -1):
            if np.isfinite(pchg[j]):
                state_direction = "UP" if pchg[j] > 0 else ("DOWN" if pchg[j] < 0 else None)
                if state_direction:
                    break
    if state_direction not in ("UP","DOWN"):
        return ("UNKNOWN_DIRECTION", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    # Strictly later PRICE observation. Same-timestamp evidence cannot leak into outcome.
    pos = int(np.searchsorted(ts_ns, anchor_ns, side="right"))
    if pos >= len(ts_ns):
        return ("NO_FOLLOW_UP", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    # Walk up to 25 subsequent PRICE observations, retaining their chronological order.
    end = min(pos + 25, len(ts_ns))
    c = close[pos:end]; h = high[pos:end]; l = low[pos:end]
    valid_h = h[np.isfinite(h)]; valid_l = l[np.isfinite(l)]; valid_c = c[np.isfinite(c)]
    if not len(valid_h) and not len(valid_l) and not len(valid_c):
        return ("NO_FOLLOW_UP", np.nan, np.nan, np.nan, np.nan, np.nan, 0, {})

    max_high = float(np.max(valid_h)) if len(valid_h) else float(np.max(valid_c))
    min_low = float(np.min(valid_l)) if len(valid_l) else float(np.min(valid_c))
    denom = abs(float(base))
    if not denom:
        return ("UNKNOWN_DIRECTION", np.nan, np.nan, np.nan, np.nan, np.nan, int(len(c)), {})

    up_exc = (max_high - base) / denom * 100
    down_exc = (base - min_low) / denom * 100
    favorable = up_exc if state_direction == "UP" else down_exc
    adverse = down_exc if state_direction == "UP" else up_exc

    checkpoints = {}
    valid_seq = c[np.isfinite(c)]
    for n in (1,2,3,5,10,20):
        if len(valid_seq) >= n:
            mv = (float(valid_seq[n-1]) - base) / denom * 100
            checkpoints[f"T{n}_move_pct"] = mv
            checkpoints[f"T{n}_same_direction"] = bool((state_direction == "UP" and mv > 0) or
                                                         (state_direction == "DOWN" and mv < 0))
        else:
            checkpoints[f"T{n}_move_pct"] = np.nan
            checkpoints[f"T{n}_same_direction"] = np.nan

    status = "SUCCESS" if favorable > 0 else "FAILURE"
    last_close = float(valid_seq[-1]) if len(valid_seq) else np.nan
    path_type = "NO_MATERIAL_MOVE"
    if favorable > 0 and np.isfinite(last_close):
        final_move = (last_close - base) / denom * 100
        favorable_final = final_move if state_direction == "UP" else -final_move
        gave_back = favorable - favorable_final
        path_type = "MOVE_THEN_RETRACE" if gave_back >= favorable * 0.5 else "MOVE_HOLDING"
    elif favorable <= 0 and adverse > 0:
        path_type = "DIRECTION_ONLY_OPPOSITE"

    return (status, favorable, adverse, max_high, min_low, last_close,
            int(len(c)), dict(checkpoints, path_type=path_type, replay_mode="ACCUMULATED_STATE_FORWARD_PRICE_STREAM"))


def add_feature_flags_vectorized(df):
    """Recreate only boolean footprint columns without row-wise apply."""
    x = df.copy()
    for k in ("ce_num","pe_num","pec_num"):
        v = pd.to_numeric(x[k], errors="coerce")
        x[k+"_500"] = v.abs().gt(500)
        x[k+"_1000"] = v.abs().gt(1000)
        x[k+"_pos500"] = v.gt(500)
        x[k+"_neg500"] = v.lt(-500)
        x[k+"_pos1000"] = v.gt(1000)
        x[k+"_neg1000"] = v.lt(-1000)
    v = pd.to_numeric(x["fut_num"], errors="coerce")
    x["fut_oi_500"] = v.abs().gt(500)
    x["fut_oi_1000"] = v.abs().gt(1000)
    x["fut_oi_pos500"] = v.gt(500)
    x["fut_oi_neg500"] = v.lt(-500)
    x["fut_oi_pos1000"] = v.gt(1000)
    x["fut_oi_neg1000"] = v.lt(-1000)
    for k in ("iv_chg","iv_chg_pct","pcr_chg","pcr_chg_pct","rollover","support_value","resistance_value"):
        if k not in x.columns:
            x[k] = np.nan
    for k in ("iv_chg","iv_chg_pct","pcr_chg","pcr_chg_pct","rollover"):
        v = pd.to_numeric(x[k], errors="coerce")
        x[k+"_pos1"] = v.gt(1)
        x[k+"_neg1"] = v.lt(-1)
        x[k+"_pos2"] = v.gt(2)
        x[k+"_neg2"] = v.lt(-2)
    # Dedicated level reports become proximity evidence only when both the
    # level and anchor close are numeric; the raw level is preserved too.
    for k, prefix in (("support_value","support"),("resistance_value","resistance")):
        lv = pd.to_numeric(x[k], errors="coerce")
        cl = pd.to_numeric(x["close"], errors="coerce")
        x[prefix+"_distance_pct"] = ((cl-lv).abs()/cl.abs()*100).where(cl.abs().gt(0) & lv.notna())
        x[prefix+"_near_1pct"] = x[prefix+"_distance_pct"].le(1).fillna(False)
        x[prefix+"_near_2pct"] = x[prefix+"_distance_pct"].le(2).fillna(False)

    v = pd.to_numeric(x["fut_pct"], errors="coerce")
    x["fut_pct_pos1"] = v.gt(1)
    x["fut_pct_neg1"] = v.lt(-1)
    x["fut_pct_pos2"] = v.gt(2)
    x["fut_pct_neg2"] = v.lt(-2)
    return x

def replay_diagnostic(obs, timeline, out_dir):
    """Audit anchor-to-later-price linkage without mining/accepting patterns.

    This is intentionally deterministic and read-only. It samples all evidence
    anchors and reports whether a strictly later price observation exists for
    the same canonical symbol/trading date. No final-state backfill is used.
    """
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    idx = build_timeline_index(timeline)
    feature_names = [
        "ce_num_pos500","ce_num_neg500","ce_num_pos1000","ce_num_neg1000",
        "pe_num_pos500","pe_num_neg500","pe_num_pos1000","pe_num_neg1000",
        "pec_num_pos500","pec_num_neg500","pec_num_pos1000","pec_num_neg1000",
        "fut_oi_pos500","fut_oi_neg500","fut_oi_pos1000","fut_oi_neg1000",
        "fut_pct_pos1","fut_pct_neg1","fut_pct_pos2","fut_pct_neg2",
        "iv_chg_pos1","iv_chg_neg1","iv_chg_pos2","iv_chg_neg2",
        "iv_chg_pct_pos1","iv_chg_pct_neg1","iv_chg_pct_pos2","iv_chg_pct_neg2",
        "pcr_chg_pos1","pcr_chg_neg1","pcr_chg_pos2","pcr_chg_neg2",
        "pcr_chg_pct_pos1","pcr_chg_pct_neg1","pcr_chg_pct_pos2","pcr_chg_pct_neg2",
        "rollover_pos1","rollover_neg1","rollover_pos2","rollover_neg2",
        "support_near_1pct","support_near_2pct","resistance_near_1pct","resistance_near_2pct",
        "volume_V75","volume_V90","volume_V95"
    ]
    b=add_feature_flags_vectorized(obs.copy())
    for c in feature_names:
        if c.startswith("volume_"):
            b[c]=b["volume_band"].eq(c[7:])
        else:
            b[c]=b[c].fillna(False).astype(bool)
    b=b.loc[b[feature_names].any(axis=1)].copy()
    rows=[]
    for r in b.itertuples(index=False):
        d=r._asdict()
        sym=d.get("symbol",""); day=str(d.get("trade_date", "")); ts=pd.Timestamp(d.get("timestamp"))
        key=(canonical_symbol(sym), day); item=idx.get(key)
        if item is None:
            rows.append({"symbol":sym,"trade_date":day,"anchor_timestamp":ts,"classification":"SYMBOL_DATE_MISMATCH","timestamp_source":str(d.get("timestamp_source", "")),"price_rows":0,"later_price_rows":0})
            continue
        ts_ns, close, high, low, pchg=item
        pos=int(np.searchsorted(ts_ns, ts.value, side="right"))
        before=max(0,pos); later=max(0,len(ts_ns)-pos)
        first_ts=pd.to_datetime(ts_ns[0]) if len(ts_ns) else pd.NaT
        last_ts=pd.to_datetime(ts_ns[-1]) if len(ts_ns) else pd.NaT
        if later>0:
            cls="ANCHOR_WITH_LATER_PRICE"
            next_ts=pd.to_datetime(ts_ns[pos])
        elif len(ts_ns) and ts.value < ts_ns[0]:
            cls="ANCHOR_BEFORE_PRICE_STREAM"
            next_ts=pd.NaT
        elif len(ts_ns) and ts.value == ts_ns[-1]:
            cls="ANCHOR_AT_LAST_PRICE"
            next_ts=pd.NaT
        else:
            cls="ANCHOR_AFTER_PRICE_STREAM"
            next_ts=pd.NaT
        rows.append({"symbol":sym,"trade_date":day,"anchor_timestamp":ts,
                     "timestamp_source":str(d.get("timestamp_source", "")),
                     "first_price_timestamp":first_ts,"last_price_timestamp":last_ts,
                     "price_rows":len(ts_ns),"price_rows_before_or_at":before,
                     "later_price_rows":later,"next_price_timestamp":next_ts,
                     "classification":cls})
    diag=pd.DataFrame(rows)
    diag.to_csv(out/"replay_linkage_diagnostic.csv",index=False)
    summary=(diag.groupby("classification",dropna=False).size().rename("anchors").reset_index())
    summary.to_csv(out/"replay_linkage_summary.csv",index=False)
    meta={"anchors":int(len(diag)),"with_later_price":int((diag.classification=="ANCHOR_WITH_LATER_PRICE").sum()),
          "no_follow_up":int(diag.classification.isin(["ANCHOR_AT_LAST_PRICE","ANCHOR_AFTER_PRICE_STREAM"]).sum()),
          "before_price_stream":int((diag.classification=="ANCHOR_BEFORE_PRICE_STREAM").sum()),
          "symbol_date_mismatch":int((diag.classification=="SYMBOL_DATE_MISMATCH").sum())}
    (out/"replay_linkage_diagnostic.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print("REPLAY_DIAGNOSTIC:",json.dumps(meta,sort_keys=True))
    return diag

def make_pattern_rows(obs, timeline, max_combo=3, out_dir=None):
    """V5 pattern discovery: discover individual footprints first, then a very small set of pairs/triples."""
    out = Path(out_dir) if out_dir is not None else None
    if out: out.mkdir(parents=True, exist_ok=True)

    feature_names = [
        "ce_num_pos500","ce_num_neg500","ce_num_pos1000","ce_num_neg1000",
        "pe_num_pos500","pe_num_neg500","pe_num_pos1000","pe_num_neg1000",
        "pec_num_pos500","pec_num_neg500","pec_num_pos1000","pec_num_neg1000",
        "fut_oi_pos500","fut_oi_neg500","fut_oi_pos1000","fut_oi_neg1000",
        "fut_pct_pos1","fut_pct_neg1","fut_pct_pos2","fut_pct_neg2",
        "iv_chg_pos1","iv_chg_neg1","iv_chg_pos2","iv_chg_neg2",
        "iv_chg_pct_pos1","iv_chg_pct_neg1","iv_chg_pct_pos2","iv_chg_pct_neg2",
        "pcr_chg_pos1","pcr_chg_neg1","pcr_chg_pos2","pcr_chg_neg2",
        "pcr_chg_pct_pos1","pcr_chg_pct_neg1","pcr_chg_pct_pos2","pcr_chg_pct_neg2",
        "rollover_pos1","rollover_neg1","rollover_pos2","rollover_neg2",
        "support_near_1pct","support_near_2pct","resistance_near_1pct","resistance_near_2pct",
        "volume_V75","volume_V90","volume_V95"
    ]
    b = obs.copy()
    for c in feature_names:
        if c.startswith("volume_"):
            b[c] = b.volume_band.eq(c[7:])
        else:
            b[c] = b[c].fillna(False).astype(bool)

    # Discovery does NOT require the composite strength bucket. Missing evidence
    # is missing evidence, not zero, and a single-source footprint is valid.
    evidence_mask = b[feature_names].any(axis=1)
    b = b.loc[evidence_mask].copy().reset_index(drop=True)
    if b.empty:
        return pd.DataFrame(), pd.DataFrame()

    idxmap = build_timeline_index(timeline)
    records = []
    memberships = []
    rows = list(b.itertuples(index=False, name=None))
    colpos = {c:i for i,c in enumerate(b.columns)}
    print(f"DISCOVERY_ANCHORS: {len(rows)}")

    for i, row in enumerate(rows):
        get=lambda c: row[colpos[c]]
        active=[f for f in feature_names if bool(get(f))]
        if not active: continue
        close=get("close")
        pdirection=get("price_direction")
        # Cached historical rows can have no canonical direction even when
        # the observation has a usable price change. For outcome discovery,
        # use the observation's own price change as a fallback.
        if pdirection not in ("UP", "DOWN"):
            try:
                pc = float(get("price_chg"))
                if pc > 0: pdirection = "UP"
                elif pc < 0: pdirection = "DOWN"
            except Exception:
                pass
        status,fav,adv,mx,mn,last,npath,extra=evaluate_anchor_fast(
            str(get("symbol")),str(get("trade_date")),
            pd.Timestamp(get("timestamp")).value,close,pdirection,idxmap)
        rec={"anchor_index":i,"symbol":str(get("symbol")),"trade_date":str(get("trade_date")),
             "timestamp":get("timestamp"),"anchor_close":close,"price_direction":pdirection,
             "status":status,"favorable_exc_pct":fav,"adverse_exc_pct":adv,"max_high":mx,
             "min_low":mn,"last_close":last,"path_observations":npath,
             "path_type":extra.pop("path_type","")}
        rec.update(extra); records.append(rec); memberships.append(active)
        if out and len(records)%10000==0: print(f"ANCHORS_EVALUATED: {len(records)}")

    anchors=pd.DataFrame(records)
    if out: anchors.to_csv(out/"anchor_outcomes.csv",index=False)
    if anchors.empty: return pd.DataFrame(),anchors

    valid=anchors.status.isin(["SUCCESS","FAILURE"])
    individual=[]
    # Membership aggregation is done from compact lists, avoiding repeated
    # full-DataFrame boolean scans.
    feature_ids={f:[] for f in feature_names}
    for i,acts in enumerate(memberships):
        for f in acts: feature_ids[f].append(i)

    for f,ids in feature_ids.items():
        if not ids: continue
        sub=anchors.iloc[ids]
        vv=sub[sub.status.isin(["SUCCESS","FAILURE"])]
        if len(vv)==0: continue
        succ=int(vv.status.eq("SUCCESS").sum()); rate=succ/len(vv)*100
        individual.append({"pattern":f,"factors":1,"events":len(sub),"valid_outcomes":len(vv),
            "success_events":succ,"failure_events":int(vv.status.eq("FAILURE").sum()),
            "success_rate_pct":rate,"symbols":int(sub.symbol.nunique()),"dates":int(sub.trade_date.nunique()),
            "no_follow_up":int(sub.status.eq("NO_FOLLOW_UP").sum()),
            "acceptance":"ACCEPTED" if rate>=80 and len(vv)>=30 and sub.trade_date.nunique()>=3 and sub.symbol.nunique()>=10 else "RESEARCH_ONLY"})
    individual_df=pd.DataFrame(individual)
    if out:
        status_counts = anchors["status"].value_counts(dropna=False).to_dict()
        (out/"anchor_status_summary.json").write_text(json.dumps({str(k):int(v) for k,v in status_counts.items()},indent=2),encoding="utf-8")
        print("ANCHOR_STATUS_SUMMARY:", json.dumps({str(k):int(v) for k,v in status_counts.items()}, sort_keys=True))
    if not individual_df.empty:
        individual_df=individual_df.sort_values(["success_rate_pct","valid_outcomes"],ascending=[False,False])
        if out: individual_df.to_csv(out/"individual_footprint_results.csv",index=False)

    # Only recurring individual candidates enter combination discovery.
    candidates=[]
    if not individual_df.empty:
        eligible=individual_df[(individual_df.valid_outcomes>=30)&(individual_df.dates>=3)&(individual_df.symbols>=10)]
        # Keep a small, evidence-ranked candidate pool. This is deliberate.
        candidates=eligible.head(12).pattern.tolist()
    patterns=individual_df.to_dict("records") if not individual_df.empty else []

    if candidates and max_combo>=2:
        postings={f:np.asarray(feature_ids[f],dtype=np.int64) for f in candidates}
        def combo_result(combo):
            ids=postings[combo[0]]
            for f in combo[1:]: ids=np.intersect1d(ids,postings[f],assume_unique=True)
            if len(ids)<30: return None
            sub=anchors.iloc[ids]; vv=sub[sub.status.isin(["SUCCESS","FAILURE"])]
            if len(vv)<30: return None
            succ=int(vv.status.eq("SUCCESS").sum()); rate=succ/len(vv)*100
            return {"pattern":" + ".join(combo),"factors":len(combo),"events":len(sub),"valid_outcomes":len(vv),
                    "success_events":succ,"failure_events":int(vv.status.eq("FAILURE").sum()),"success_rate_pct":rate,
                    "symbols":int(sub.symbol.nunique()),"dates":int(sub.trade_date.nunique()),
                    "no_follow_up":int(sub.status.eq("NO_FOLLOW_UP").sum()),
                    "acceptance":"ACCEPTED" if rate>=80 and len(vv)>=30 and sub.trade_date.nunique()>=3 and sub.symbol.nunique()>=10 else "RESEARCH_ONLY"}
        pair_rows=[]
        for combo in itertools.combinations(candidates,2):
            r=combo_result(combo)
            if r: pair_rows.append(r)
        pair_df=pd.DataFrame(pair_rows)
        if out: pair_df.to_csv(out/"pair_results.csv",index=False)
        if not pair_df.empty:
            pair_df=pair_df.sort_values(["success_rate_pct","valid_outcomes"],ascending=[False,False])
            patterns.extend(pair_df.to_dict("records"))
            if max_combo>=3:
                top=set()
                for p in pair_df.head(6).pattern: top.update(p.split(" + "))
                for combo in itertools.combinations(sorted(top),3):
                    r=combo_result(combo)
                    if r: patterns.append(r)

    pattern_df=pd.DataFrame(patterns)
    if not pattern_df.empty:
        pattern_df=pattern_df.sort_values(["acceptance","success_rate_pct","valid_outcomes"],ascending=[True,False,False])
    if out:
        pattern_df.to_csv(out/"pattern_results.csv",index=False)
        (out/"study_summary.json").write_text(json.dumps({
            "anchors":int(len(anchors)),"valid_outcomes":int(valid.sum()),
            "individual_candidates":int(len(candidates)),"pattern_results":int(len(pattern_df)),
            "accepted_patterns":int(pattern_df.acceptance.eq("ACCEPTED").sum()) if not pattern_df.empty else 0,
            "discovery_filter":"specific evidence footprint only; composite strength bucket not required",
            "acceptance_rule":">=80% valid favorable-path rate AND >=30 valid outcomes AND >=3 dates AND >=10 symbols"
        },indent=2),encoding="utf-8")
    return pattern_df,anchors


# ---- Repository-wide baseline / source census (offline, read-only) ----
BROAD_FAMILY_TOKENS = {
    "FUTURES": ("futuresoi", "futureoi", "futures_oi"),
    "OPTIONS": ("option", "daywise_price_and_oi", "openinterest", "oi_"),
    "VOLUME": ("volume", "spike", "volumeandoi"),
    "IVR": ("ivr",),
    "IVP": ("ivp",),
    "PCR": ("pcr",),
    "SUPPORT": ("support",),
    "RESISTANCE": ("resistance",),
    "BREAKOUT": ("breakout",),
    "SECTOR": ("sector_summary", "sectorsummary"),
}


def broad_source_family(path: Path) -> str:
    n = path.name.lower().replace(" ", "_")
    for fam, toks in BROAD_FAMILY_TOKENS.items():
        if any(t in n for t in toks):
            return fam
    return "OTHER"


def baseline_schema_probe(path: Path):
    """Cheap one-file schema probe; reads headers/first sheet only."""
    fam = broad_source_family(path)
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:
        return {"family": fam, "readable": False, "sheets": 0, "symbol": False,
                "columns": 0, "error": type(exc).__name__}
    found_symbol = False
    ncols = 0
    matched = set()
    try:
        for sh in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sh, nrows=5)
            if df.empty:
                continue
            cols = list(df.columns)
            ncols = max(ncols, len(cols))
            if exact(cols, ["Symbol"]):
                found_symbol = True
            nc = {norm(c) for c in cols}
            probes = {
                "price": ("price", "price chg", "price chg (%)", "close", "open", "high", "low"),
                "volume": ("volume chg (%)", "volume chg", "volume change"),
                "ce": ("tol ce oi chg", "tot ce oi chg"),
                "pe": ("tol pe oi chg", "tot pe oi chg"),
                "pec": ("tol pe-ce oi chg", "tot pe-ce oi chg"),
                "fut_oi": ("oi chg",),
                "fut_pct": ("oi chg %",),
                "fut_state": ("fut buildup", "buildup"),
                "iv_chg": ("iv chg", "iv change"),
                "iv_chg_pct": ("iv chg %", "iv chg (%)", "iv change %"),
                "pcr_chg": ("pcr chg", "pcr change"),
                "pcr_chg_pct": ("pcr chg %", "pcr chg (%)", "pcr change %"),
                "ivr": ("ivr", "iv rank"),
                "ivp": ("ivp", "iv percentile"),
                "pcr": ("pcr", "pcr chg", "pcr change"),
                "support": ("support", "support price", "support level"),
                "resistance": ("resistance", "resistance price", "resistance level"),
                "rollover": ("rollover (%)", "rollover", "rollover %"),
                "buildup": ("buildup", "fut buildup"),
            }
            for role, aliases in probes.items():
                if any(a in nc for a in aliases):
                    matched.add(role)
            # Dedicated reports are role-bearing by filename even when the
            # workbook uses a non-standard level column name. This is distinct
            # from finding a canonical value column.
            if fam == "SUPPORT":
                matched.add("support_source")
            if fam == "RESISTANCE":
                matched.add("resistance_source")
            if fam == "IVR":
                matched.add("ivr_source")
            if fam == "IVP":
                matched.add("ivp_source")
    except Exception as exc:
        return {"family": fam, "readable": False, "sheets": len(xl.sheet_names),
                "symbol": found_symbol, "columns": ncols, "error": type(exc).__name__}
    return {"family": fam, "readable": True, "sheets": len(xl.sheet_names),
            "symbol": found_symbol, "columns": ncols, "matched": ";".join(sorted(matched))}


def run_baseline(root: Path, out: Path):
    """Repository readiness gate. No pattern mining and no production writes."""
    files = sorted(root.rglob("*.xlsx"))
    rows = []
    for i, path in enumerate(files, 1):
        rows.append({"file": str(path), "name": path.name, **baseline_schema_probe(path)})
        if i % 500 == 0:
            print(f"BASELINE_FILES_PROBED: {i}/{len(files)}")
    inv = pd.DataFrame(rows)
    # Always materialize the expected columns, including the zero-file case.
    # This keeps the baseline gate deterministic when the supplied repository
    # root contains no discoverable XLSX files.
    expected_cols = ["file", "name", "family", "readable", "sheets", "symbol", "columns", "matched", "error"]
    for col in expected_cols:
        if col not in inv.columns:
            inv[col] = pd.Series(dtype="object")
    inv.to_csv(out / "source_baseline_inventory.csv", index=False)
    if inv.empty:
        fam = pd.DataFrame(columns=["family", "files", "readable", "symbol_bearing", "sheets"])
    else:
        fam = (inv.groupby("family", dropna=False)
               .agg(files=("file", "size"), readable=("readable", "sum"),
                    symbol_bearing=("symbol", "sum"), sheets=("sheets", "sum"))
               .reset_index())
    fam.to_csv(out / "source_baseline_family_summary.csv", index=False)
    # Count availability of important roles without deciding that any role is predictive.
    role_counts = {}
    for role in ["price","volume","ce","pe","pec","fut_oi","fut_pct","fut_state",
                 "iv_chg","iv_chg_pct","pcr_chg","pcr_chg_pct","ivr","ivp","pcr",
                 "support","support_source","resistance","resistance_source","rollover","buildup"]:
        role_counts[role] = int(inv.get("matched", pd.Series(dtype=str)).fillna("").str.split(";").map(lambda x: role in x).sum())
    cache_candidates = [
        out / "canonical_strength_observations.csv",
        out.parent / "data_strength_combination_study" / "canonical_strength_observations.csv",
        out.parent / "straddle_historical_research" / "canonical_observations.csv",
    ]
    existing = [str(x) for x in cache_candidates if x.exists()]
    ready_reasons = []
    if not files: ready_reasons.append("NO_XLSX_SOURCES")
    if int(inv.readable.sum()) == 0: ready_reasons.append("NO_READABLE_SOURCES")
    if int(inv.symbol.sum()) == 0: ready_reasons.append("NO_SYMBOL_BEARING_SOURCES")
    if role_counts["price"] == 0: ready_reasons.append("NO_PRICE_FIELDS")
    status = "READY_FOR_FINAL_PATTERN_RUN" if not ready_reasons else "NOT_READY"
    meta = {
        "status": status,
        "production_modified": False,
        "files": len(files),
        "readable_files": int(inv.readable.sum()),
        "symbol_bearing_files": int(inv.symbol.sum()),
        "families": int(inv.family.nunique()),
        "source_root": str(root.resolve()),
        "role_file_counts": role_counts,
        "existing_reusable_caches": existing,
        "final_run_allowed": status == "READY_FOR_FINAL_PATTERN_RUN",
        "final_run_policy": "Run final discovery only after this baseline is reviewed; baseline itself performs no outcome mining.",
        "timestamp_policy": "Use filesystem creation time only where source timestamp is not authoritative.",
        "missing_evidence_policy": "Missing is missing, never zero.",
        "leakage_policy": "Only evidence available at/before anchor may enter discovery."
    }
    (out / "baseline_readiness.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=str))
    return status

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Permanent raw repository root")
    ap.add_argument("--out", required=True, help="Offline research output directory")
    ap.add_argument("--max-combination", type=int, default=3)
    ap.add_argument("--mode", choices=["baseline", "final"], default="baseline")
    ap.add_argument("--diagnostic", action="store_true", help="Run replay linkage diagnostic before pattern mining")
    args = ap.parse_args()

    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.mode == "baseline":
        run_baseline(root, out)
        return

    readiness = out / "baseline_readiness.json"
    if not readiness.exists():
        print("FINAL_RUN_BLOCKED: baseline_readiness.json not found. Run --mode baseline first.")
        return
    try:
        baseline = json.loads(readiness.read_text(encoding="utf-8"))
    except Exception:
        baseline = {}
    if baseline.get("status") != "READY_FOR_FINAL_PATTERN_RUN":
        print("FINAL_RUN_BLOCKED: baseline status is not READY_FOR_FINAL_PATTERN_RUN")
        return
    baseline_root = str(baseline.get("source_root", ""))
    try:
        current_root = str(root.resolve())
    except Exception:
        current_root = str(root)
    if baseline_root and baseline_root != current_root:
        print(f"FINAL_RUN_BLOCKED: baseline source_root differs from requested root: {baseline_root} != {current_root}")
        return

    cache = out / "canonical_strength_observations.csv"
    cache_manifest = out / "canonical_strength_observations_manifest.json"
    required = {"symbol","trade_date","timestamp","family","close","price_chg",
                "price_direction","strength_bucket","volume_band",
                "iv_chg","pcr_chg","support_value","resistance_value"}
    obs = None
    CACHE_VERSION = "V6_5_WORKBOOK_TIMESTAMP_FORWARD_REPLAY"

    # Reuse only a cache created with the current report-timestamp resolver.
    # Older V6 caches used filesystem creation time and therefore cannot be
    # safely reused for chronological outcome reconstruction.
    if cache.exists() and cache_manifest.exists():
        try:
            manifest = json.loads(cache_manifest.read_text(encoding="utf-8"))
            probe = pd.read_csv(cache, nrows=1)
            if (manifest.get("cache_version") == CACHE_VERSION and
                    required.issubset(set(probe.columns))):
                print("CANONICAL_CACHE_FOUND: reusing current timestamp-resolved evidence")
                obs = pd.read_csv(cache, low_memory=False)
                obs["timestamp"] = pd.to_datetime(obs["timestamp"], errors="coerce")
                print(f"CANONICAL_CACHE_ROWS: {len(obs)}")
        except Exception:
            obs = None
    elif cache.exists():
        print("CANONICAL_CACHE_STALE: rebuilding with report timestamps")

    if obs is None:
        files = list(root.rglob("*.xlsx"))
        all_frames = []
        for i, p in enumerate(files, 1):
            rr = read_file(p)
            if rr:
                all_frames.extend(rr)
            if i % 500 == 0:
                print(f"SOURCE_FILES_READ: {i}/{len(files)}")
        if not all_frames:
            print(json.dumps({"status":"NO_DATA","production_modified":False}, indent=2))
            return

        obs = pd.concat(all_frames, ignore_index=True)
        obs["trade_date"] = obs["timestamp"].dt.date.astype(str)
        obs = obs.dropna(subset=["symbol","timestamp"]).copy()

        flags = obs.apply(feature_flags, axis=1, result_type="expand")
        obs = pd.concat([obs, flags], axis=1)
        obs, volume_meta = build_strength(obs)
        obs = add_feature_flags_vectorized(obs)

        cols = [
            "symbol","trade_date","timestamp","timestamp_source","family","source_file","sheet",
            "open","high","low","close","price_chg","price_chg_pct",
            "volume_pct","volume_band",
            "ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct",
            "fut_num","fut_pct","fut_state",
            "iv_chg","iv_chg_pct","pcr_chg","pcr_chg_pct","rollover",
            "support_value","resistance_value","support_distance_pct","resistance_distance_pct",
            "price_direction","option_direction","fut_direction",
            "direction_agreement","core_evidence_count","magnitude_count",
            "persistent","strength_bucket"
        ]
        obs[cols].to_csv(cache, index=False)
        cache_manifest.write_text(json.dumps({
            "cache_version": CACHE_VERSION,
            "timestamp_source": "report filename/path date-time when present; filesystem creation time only as fallback",
            "rows": int(len(obs)),
            "source_root": str(root.resolve()),
        }, indent=2), encoding="utf-8")
        print(f"CANONICAL_BUILD_COMPLETE: {len(obs)} rows")
    else:
        # Cached canonical already contains derived strength fields.
        volume_meta = {"volume_abs_quantiles": {}}

    obs["timestamp"] = pd.to_datetime(obs["timestamp"], errors="coerce")
    obs["trade_date"] = obs["trade_date"].astype(str)
    obs = add_feature_flags_vectorized(obs)
    timeline = dedup_timeline(obs)
    timeline.to_csv(out/"deduplicated_price_timeline.csv", index=False)
    price_keys = int(timeline[["symbol_key","trade_date"]].drop_duplicates().shape[0]) if not timeline.empty else 0
    print(f"TIMELINE_READY: {len(timeline)} rows")
    print(f"PRICE_STREAM_KEYS: {price_keys}")
    print(f"PRICE_STREAM_SYMBOLS: {timeline.symbol_key.nunique() if not timeline.empty else 0}")

    if args.diagnostic:
        replay_diagnostic(obs, timeline, out)
        print("DIAGNOSTIC_COMPLETE: replay linkage only; pattern mining skipped")
        return

    patterns, anchors = make_pattern_rows(obs, timeline, args.max_combination, out)
    if patterns.empty:
        patterns = pd.DataFrame(columns=[
            "pattern","factors","events","valid_outcomes","success_events","failure_events",
            "success_rate_pct","symbols","dates","no_follow_up","acceptance"
        ])
    patterns = patterns.sort_values(
        ["acceptance","success_rate_pct","valid_outcomes","dates"],
        ascending=[True,False,False,False]
    )
    patterns.to_csv(out/"specific_combination_patterns.csv", index=False)

    if not patterns.empty:
        accepted = patterns[patterns.acceptance.eq("ACCEPTED")]
        research = patterns[patterns.acceptance.ne("ACCEPTED")]
    else:
        accepted = research = patterns
    accepted.to_csv(out/"accepted_patterns.csv", index=False)
    research.to_csv(out/"research_only_patterns.csv", index=False)

    strength_summary = (
        obs.groupby("strength_bucket")
        .agg(observations=("symbol","size"),symbols=("symbol","nunique"),dates=("trade_date","nunique"),
             avg_core_evidence=("core_evidence_count","mean"),avg_magnitude=("magnitude_count","mean"))
        .reset_index()
    )
    strength_summary.to_csv(out/"data_strength_summary.csv", index=False)

    family_summary = (
        obs.groupby(["family","price_direction"], dropna=False)
        .agg(observations=("symbol","size"),symbols=("symbol","nunique"),dates=("trade_date","nunique"))
        .reset_index()
    )
    family_summary.to_csv(out/"source_family_summary.csv", index=False)

    meta = {
        "status":"DATA_STRENGTH_COMBINATION_STUDY_COMPLETE",
        "version":"V6_5_WORKBOOK_TIMESTAMP_FORWARD_REPLAY",
        "production_modified":False,
        "observations":len(obs),
        "symbols":int(obs.symbol.nunique()),
        "dates":int(obs.trade_date.nunique()),
        "timestamped":int(obs.timestamp.notna().sum()),
        "strength_filtered_anchors":int(obs.strength_bucket.isin(["MODERATE","STRONG","VERY_STRONG"]).sum()),
        "patterns_tested":int(len(patterns)),
        "accepted_patterns":int(len(accepted)),
        "acceptance_rule":">=80% valid favorable-path rate AND >=30 valid outcomes AND >=3 dates AND >=10 symbols",
        "no_follow_up_is_not_failure":True,
        "volume_thresholds":"distribution-derived quantile bands; no fixed final volume threshold",
        "futures_mapping":"FuturesOI primary OI Chg / OI Chg %, state from Fut Buildup/Buildup; .1/.2/.3 excluded",
        "options_mapping":"Primary Daywise/option reports: CE/PE/PE-CE OI change NUMBER and % kept as separate fields",
        "iv_mapping":"IV Chg and IV Chg % are read from the primary workbook when present; IVR/IVP remain distinct",
        "support_resistance_mapping":"Dedicated Support/Resistance filenames define source family; named level columns are used when available and missing level values remain missing",
        "source_discovery":"Report filename/family plus exact workbook schema; no single-workbook assumption",
        "production_scope":"offline research only; no SDL dashboard/app modification",
        "discovery_method":"individual footprints first; limited recurring candidates for combinations; composite strength is descriptive only",
        "timestamp_resolution":"report filename/path timestamp first; filesystem creation time only when no authoritative report timestamp exists",
        "outcome_linkage":"accumulated state at/before anchor + strictly later canonical price observations; forward-only replay; no-follow-up and unknown direction remain separate"
    }
    (out/"research_summary.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=str))

if __name__ == "__main__":
    main()
