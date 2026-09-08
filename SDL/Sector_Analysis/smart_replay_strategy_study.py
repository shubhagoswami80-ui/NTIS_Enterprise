#!/usr/bin/env python3
"""
NTIS SDL Smart Replay & Intraday Hit Discovery Engine

Purpose
-------
Repair/validate historical forward replay with minimum I/O, then discover
ORB + supporting evidence candidates in the 67-80% historical hit zone.

Design goals
------------
* Reuse existing canonical/clean timeline caches whenever possible.
* Do not rescan 4,000+ XLSX files unless the cache is absent.
* Automatically identify the best intraday stock-price stream instead of
  assuming every OHLC-bearing row is a usable future-price observation.
* Forward-only replay: evidence at T can only explain strictly later price.
* Missing evidence != zero; no-follow-up/unknown are excluded from failures.
* Search individual footprints, then bounded 2/3/4-factor combinations.
* Hard final gate remains >=80%, >=30 outcomes, >=3 dates, >=10 symbols.
* 67-79% recurring candidates are retained as optimization candidates.
* No dashboard changes.

This is research code. It does not generate execution orders or trade advice.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

VERSION = "V4.0_MULTI_WINDOW_HIT_STUDY"

FINAL_RATE = 0.80
HIT_FLOOR = 0.67
MIN_OUTCOMES = 30
MIN_DATES = 3
MIN_SYMBOLS = 10

FEATURE_COLUMNS = [
    "orb_up", "orb_down",
    "fut_lb", "fut_sb", "fut_sc",
    "fut_gt500", "fut_gt1000", "fut_lt500", "fut_lt1000",
    "fut_pct_gt1", "fut_pct_gt2", "fut_pct_lt1", "fut_pct_lt2",
    "ce_gt500", "ce_gt1000", "ce_lt500", "ce_lt1000",
    "pe_gt500", "pe_gt1000", "pe_lt500", "pe_lt1000",
    "pec_gt500", "pec_gt1000", "pec_lt500", "pec_lt1000",
    "iv_up", "iv_down", "iv_pct_up", "iv_pct_down",
    "straddle_up", "straddle_down",
    "volume_up", "volume_down",
    "pcr_up", "pcr_down",
    "buildup_present", "support_present", "resistance_present",
    "direction_agree", "multi_source",
]

EVIDENCE_COLS = {
    "fut_num": "fut_num", "fut_pct": "fut_pct", "fut_state": "fut_state",
    "ce_num": "ce_num", "pe_num": "pe_num", "pec_num": "pec_num",
    "ce_pct": "ce_pct", "pe_pct": "pe_pct", "pec_pct": "pec_pct",
    "volume_pct": "volume_pct", "iv_chg": "iv_chg", "iv_chg_pct": "iv_chg_pct",
    "pcr_chg": "pcr_chg", "pcr_chg_pct": "pcr_chg_pct",
    "straddle_pct": "straddle_pct", "straddle": "straddle",
    "fut_state": "fut_state", "buildup": "buildup",
    "support": "support", "resistance": "resistance",
}


def norm_symbol(v) -> str:
    if pd.isna(v):
        return ""
    return re.sub(r"[^A-Z0-9&_-]", "", str(v).upper().strip())


def norm_col(c) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")


def as_num(s, index=None):
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    if index is None:
        index = pd.RangeIndex(1)
    return pd.Series(s, index=index, dtype="float64")


def parse_timestamp_series(df: pd.DataFrame) -> pd.Series:
    """Prefer explicit row timestamps. Never attach today's date to time-only values."""
    cols = {norm_col(c): c for c in df.columns}
    for key in ("timestamp", "datetime", "date_time", "observation_timestamp", "time_stamp"):
        if key in cols:
            x = pd.to_datetime(df[cols[key]], errors="coerce")
            if x.notna().any():
                return x
    date_col = next((cols[k] for k in ("trade_date", "trading_date", "date") if k in cols), None)
    time_col = next((cols[k] for k in ("time", "observation_time", "report_time") if k in cols), None)
    if date_col and time_col:
        d = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
        t = df[time_col].astype(str).str.strip()
        return pd.to_datetime(d + " " + t, errors="coerce")
    if date_col:
        return pd.to_datetime(df[date_col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")


def load_table(path: Path, usecols=None) -> pd.DataFrame:
    return pd.read_csv(path, usecols=usecols, low_memory=False)


def find_cache(root: Path) -> Path | None:
    candidates = [
        root / "SDL" / "Sector_Analysis" / ".sector_intelligence" / "data_strength_combination_study" / "canonical_strength_observations.csv",
        root / "SDL" / "Sector_Analysis" / ".sector_intelligence" / "broad_source_pattern_research" / "canonical_observations.csv",
        root / "SDL" / "Sector_Analysis" / ".sector_intelligence" / "straddle_historical_research" / "canonical_observations.csv",
        root / "SDL" / "Sector_Analysis" / ".sector_intelligence" / "data_strength_combination_study" / "clean_intraday_timeline.csv",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 1000:
            return p
    return None


def load_canonical(cache: Path) -> pd.DataFrame:
    # Read only columns that exist; canonical cache is the expensive asset, so do it once.
    df = pd.read_csv(cache, low_memory=False)
    rename = {c: norm_col(c) for c in df.columns}
    df = df.rename(columns=rename)
    aliases = {
        "symbol": ["symbol"], "trade_date": ["trade_date", "trading_date", "date"],
        "timestamp": ["timestamp", "datetime", "date_time"],
        "family": ["family", "source_family"],
        "open": ["open"], "high": ["high"], "low": ["low"], "close": ["close"],
        "price_chg": ["price_chg", "price_change"], "price_chg_pct": ["price_chg_pct", "price_change_pct"],
        "volume_pct": ["volume_pct", "volume_chg_pct"],
        "ce_num": ["ce_num"], "pe_num": ["pe_num"], "pec_num": ["pec_num"],
        "ce_pct": ["ce_pct"], "pe_pct": ["pe_pct"], "pec_pct": ["pec_pct"],
        "fut_num": ["fut_num"], "fut_pct": ["fut_pct"], "fut_state": ["fut_state"],
        "iv_chg": ["iv_chg"], "iv_chg_pct": ["iv_chg_pct"],
        "pcr_chg": ["pcr_chg", "pcr_change"], "pcr_chg_pct": ["pcr_chg_pct", "pcr_change_pct"],
        "straddle_pct": ["straddle_pct", "atm_straddle_pct"],
        "straddle": ["straddle", "atm_straddle"],
        "buildup": ["buildup"], "support": ["support"], "resistance": ["resistance"],
    }
    out = pd.DataFrame(index=df.index)
    for dst, opts in aliases.items():
        src = next((x for x in opts if x in df.columns), None)
        out[dst] = df[src] if src else np.nan
    out["symbol"] = out["symbol"].map(norm_symbol)
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    for c in out.columns:
        if c not in ("symbol", "timestamp", "trade_date", "family", "fut_state", "buildup"):
            out[c] = as_num(out[c])
    out["family"] = out["family"].astype(str).str.upper()
    out = out[out["symbol"].ne("") & out["timestamp"].notna()].copy()
    return out.sort_values(["symbol", "trade_date", "timestamp"], kind="mergesort")


def price_stream_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Score OHLC-bearing source families by actual intraday density."""
    x = df.copy()
    x = x[x[["open", "high", "low", "close"]].notna().all(axis=1)]
    bad = x["family"].str.contains("FUTURE|OPTION|SECTOR|SUPPORT|RESIST|PCR", na=False)
    x = x[~bad]
    if x.empty:
        return pd.DataFrame(columns=["family", "rows", "pairs", "multi_ts_pairs", "median_obs_per_day", "score"])
    g = x.groupby(["family", "symbol", "trade_date"], sort=False)
    pair_counts = g.size().rename("obs").reset_index()
    stats = []
    for fam, q in pair_counts.groupby("family"):
        pairs = len(q)
        multi = int((q["obs"] > 1).sum())
        med = float(q["obs"].median()) if pairs else 0.0
        rows = int(q["obs"].sum())
        # Reward repeated intraday observations, not raw row count.
        score = math.log1p(med) * (multi / max(pairs, 1)) * math.log1p(pairs)
        stats.append([fam, rows, pairs, multi, med, score])
    return pd.DataFrame(stats, columns=["family", "rows", "pairs", "multi_ts_pairs", "median_obs_per_day", "score"]).sort_values("score", ascending=False)


def choose_price_stream(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cand = price_stream_candidates(df)
    # Important fallback: the canonical cache may contain complete OHLC rows
    # but no usable labelled source family (for example family may be empty or
    # all rows may have been normalized into a generic family).  Do not reject
    # a proven OHLC timeline merely because family-based scoring is unavailable.
    if cand.empty:
        ohlc = df[df[["open", "high", "low", "close"]].notna().all(axis=1)].copy()
        ohlc = ohlc.drop_duplicates(["symbol", "trade_date", "timestamp"], keep="last")
        if not ohlc.empty:
            return (ohlc.sort_values(["symbol", "trade_date", "timestamp"], kind="mergesort"),
                    {"status": "OK", "selected_family": "ALL_OHLC_CANONICAL",
                     "candidate_count": 0, "selection_reason": "complete canonical OHLC fallback"})
        return pd.DataFrame(), {"status": "NO_OHLC_PRICE_CANDIDATE"}
    best = cand.iloc[0]
    fam = best["family"]
    stream = df[(df["family"] == fam) & df[["open", "high", "low", "close"]].notna().all(axis=1)].copy()
    # If the best family is not genuinely intraday, retain all OHLC rows from the
    # top two families only when they have >1 observation/day. This avoids using EOD
    # summaries as the future-price stream.
    if best["median_obs_per_day"] <= 1:
        usable = cand[cand["median_obs_per_day"] > 1].head(2)["family"].tolist()
        if usable:
            stream = df[df["family"].isin(usable) & df[["open", "high", "low", "close"]].notna().all(axis=1)].copy()
            fam = ",".join(usable)
    stream = stream.drop_duplicates(["symbol", "trade_date", "timestamp"], keep="last")
    meta = {"status": "OK", "selected_family": fam, "candidate_count": len(cand), "candidates": cand.to_dict("records")}
    return stream.sort_values(["symbol", "trade_date", "timestamp"], kind="mergesort"), meta


def build_price_index(price: pd.DataFrame):
    idx = {}
    for key, g in price.groupby(["symbol", "trade_date"], sort=False):
        idx[key] = g.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    return idx


def replay_diagnostic(evidence: pd.DataFrame, price_idx: dict) -> dict:
    keys = evidence[["symbol", "trade_date"]].drop_duplicates().itertuples(index=False, name=None)
    before = nofollow = later = 0
    for sym, d in keys:
        pg = price_idx.get((sym, d))
        if pg is None or pg.empty:
            continue
        et = evidence.loc[(evidence.symbol == sym) & (evidence.trade_date == d), "timestamp"]
        if et.empty:
            continue
        pmin, pmax = pg.timestamp.min(), pg.timestamp.max()
        if et.min() < pmax:
            later += 1
        else:
            nofollow += 1
        if et.max() > pmin:
            before += 1
    return {"symbol_date_keys": len(price_idx), "keys_with_evidence_before_price_end": later,
            "keys_with_evidence_after_price_start": before, "keys_without_later_price": nofollow}


def orb_anchors(price_idx: dict, window_min: int = 15) -> pd.DataFrame:
    rows = []
    for (sym, d), g in price_idx.items():
        if len(g) < 3:
            continue
        t0 = g.timestamp.iloc[0]
        cutoff = t0 + pd.Timedelta(minutes=window_min)
        orb = g[g.timestamp <= cutoff]
        if len(orb) < 2:
            continue
        hi, lo = float(orb.high.max()), float(orb.low.min())
        rng = hi - lo
        if not np.isfinite(rng) or rng <= 0:
            continue
        after = g[g.timestamp > cutoff]
        if after.empty:
            continue
        up = after[after.close > hi]
        dn = after[after.close < lo]
        for direction, hit in (("UP", up.head(1)), ("DOWN", dn.head(1))):
            if hit.empty:
                continue
            r = hit.iloc[0]
            rows.append({"symbol": sym, "trade_date": d, "anchor_time": r.timestamp,
                         "orb_high": hi, "orb_low": lo, "orb_range": rng,
                         "breakout_price": float(r.close), "orb_direction": direction})
    return pd.DataFrame(rows)


def latest_state(evidence: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    # Merge all evidence rows <= anchor and keep latest non-null value per feature.
    if anchors.empty:
        return anchors
    e = evidence.copy()
    a = anchors.copy()
    out = []
    grouped = {(s, d): g for (s, d), g in e.groupby(["symbol", "trade_date"], sort=False)}
    for ar in a.itertuples(index=False):
        g = grouped.get((ar.symbol, ar.trade_date))
        row = ar._asdict()
        if g is None:
            out.append(row); continue
        g = g[g.timestamp <= ar.anchor_time]
        if g.empty:
            out.append(row); continue
        for c in EVIDENCE_COLS:
            if c not in g.columns:
                continue
            v = g[["timestamp", c]].dropna()
            if not v.empty:
                row[c] = v.iloc[-1][c]
        out.append(row)
    return pd.DataFrame(out)


def add_features(a: pd.DataFrame) -> pd.DataFrame:
    x = a.copy()
    for c in FEATURE_COLUMNS:
        x[c] = False
    d = x.orb_direction.eq("UP")
    x.loc[d, "orb_up"] = True
    x.loc[~d, "orb_down"] = True
    state = x.get("fut_state", pd.Series(index=x.index, dtype=object)).astype(str).str.upper()
    for s in ("LB", "SB", "SC"):
        x.loc[state.eq(s), "fut_" + s.lower()] = True
    f = as_num(x.get("fut_num", np.nan), x.index); fp = as_num(x.get("fut_pct", np.nan), x.index)
    for name, mask in [("fut_gt500", f > 500), ("fut_gt1000", f > 1000), ("fut_lt500", f < -500), ("fut_lt1000", f < -1000),
                       ("fut_pct_gt1", fp > 1), ("fut_pct_gt2", fp > 2), ("fut_pct_lt1", fp < -1), ("fut_pct_lt2", fp < -2)]: x.loc[mask.fillna(False), name] = True
    for base in ("ce", "pe", "pec"):
        v = as_num(x.get(base + "_num", np.nan), x.index)
        for name, mask in [(base+"_gt500", v > 500), (base+"_gt1000", v > 1000), (base+"_lt500", v < -500), (base+"_lt1000", v < -1000)]: x.loc[mask.fillna(False), name] = True
    iv = as_num(x.get("iv_chg", np.nan), x.index); ivp = as_num(x.get("iv_chg_pct", np.nan), x.index)
    x.loc[(iv > 0).fillna(False), "iv_up"] = True; x.loc[(iv < 0).fillna(False), "iv_down"] = True
    x.loc[(ivp > 0).fillna(False), "iv_pct_up"] = True; x.loc[(ivp < 0).fillna(False), "iv_pct_down"] = True
    sp = as_num(x.get("straddle_pct", np.nan), x.index); sv = as_num(x.get("straddle", np.nan), x.index)
    # Prefer percentage when available; raw straddle is directional only as a change proxy when no % exists.
    sx = sp.where(sp.notna(), sv)
    x.loc[(sx > 0).fillna(False), "straddle_up"] = True; x.loc[(sx < 0).fillna(False), "straddle_down"] = True
    vol = as_num(x.get("volume_pct", np.nan), x.index); pcr = as_num(x.get("pcr_chg_pct", np.nan), x.index);
    x.loc[(vol > 0).fillna(False), "volume_up"] = True; x.loc[(vol < 0).fillna(False), "volume_down"] = True
    x.loc[(pcr > 0).fillna(False), "pcr_up"] = True; x.loc[(pcr < 0).fillna(False), "pcr_down"] = True
    x["buildup_present"] = x.get("buildup", pd.Series(index=x.index)).notna() & x.get("buildup", pd.Series(index=x.index)).astype(str).ne("nan")
    x["support_present"] = as_num(x.get("support", np.nan), x.index).notna()
    x["resistance_present"] = as_num(x.get("resistance", np.nan), x.index).notna()
    agree = []
    for r in x.itertuples(index=False):
        od = r.orb_direction
        signs = []
        if getattr(r, "fut_lb", False): signs.append("UP")
        if getattr(r, "fut_sb", False) or getattr(r, "fut_sc", False): signs.append("DOWN")
        for base in ("ce_num", "pe_num", "pec_num"):
            v = getattr(r, base, np.nan)
            if pd.notna(v): signs.append("UP" if v > 0 else "DOWN" if v < 0 else "FLAT")
        agree.append(any(s == od for s in signs))
    x["direction_agree"] = agree
    x["multi_source"] = x[["fut_lb","fut_sb","fut_sc","ce_gt500","ce_gt1000","ce_lt500","ce_lt1000","pe_gt500","pe_gt1000","pe_lt500","pe_lt1000","pec_gt500","pec_gt1000","pec_lt500","pec_lt1000","volume_up","volume_down","iv_up","iv_down","straddle_up","straddle_down"]].sum(axis=1) >= 2
    return x


def outcome_for_anchor(ar, pg: pd.DataFrame) -> dict:
    later = pg[pg.timestamp > ar.anchor_time]
    if later.empty:
        return {"status": "NO_FOLLOW_UP"}
    direction = ar.orb_direction
    entry = float(ar.breakout_price)
    rng = float(ar.orb_range)
    if not np.isfinite(entry) or not np.isfinite(rng) or rng <= 0:
        return {"status": "UNKNOWN"}
    if direction == "UP":
        fav = ((later.high - entry) / entry * 100).max()
        adv = ((later.low - entry) / entry * 100).min()
        final = (float(later.close.iloc[-1]) - entry) / entry * 100
        fav_abs = (later.high - entry).max()
        adverse_abs = (entry - later.low).max()
    else:
        fav = ((entry - later.low) / entry * 100).max()
        adv = ((entry - later.high) / entry * 100).min()
        final = (entry - float(later.close.iloc[-1])) / entry * 100
        fav_abs = (entry - later.low).max()
        adverse_abs = (later.high - entry).max()
    # Research outcomes at several ORB-range milestones; no single threshold is frozen.
    stage = {f"reached_{m}x": bool(fav_abs >= m * rng) for m in (0.5, 1.0, 1.5)}
    holding = final > 0 if direction == "UP" else final > 0
    if stage["reached_1.0x"] and final > 0:
        path = "MOVE_HOLDING"
    elif stage["reached_1.0x"]:
        path = "MOVE_THEN_RETRACE"
    elif stage["reached_0.5x"]:
        path = "PARTIAL_MOVE"
    elif fav_abs > 0:
        path = "NO_MATERIAL_MOVE"
    else:
        path = "OPPOSITE_MOVE"
    return {"status": "VALID", "favorable_pct": fav, "adverse_pct": adv,
            "final_pct": final, "favorable_abs": fav_abs, "adverse_abs": adverse_abs,
            "path_class": path, **stage}


def attach_outcomes(features: pd.DataFrame, price_idx: dict) -> pd.DataFrame:
    rows=[]
    for r in features.itertuples(index=False):
        o=outcome_for_anchor(r, price_idx.get((r.symbol,r.trade_date), pd.DataFrame()))
        row=r._asdict(); row.update(o); rows.append(row)
    return pd.DataFrame(rows)


def discover_patterns(df: pd.DataFrame, max_k: int = 4) -> pd.DataFrame:
    bool_cols = [c for c in FEATURE_COLUMNS if c in df.columns and df[c].dtype == bool]
    # Only retain features that occur often enough to avoid a combinatorial explosion.
    freq = {c: int(df[c].sum()) for c in bool_cols}
    bool_cols = [c for c in bool_cols if freq[c] >= MIN_OUTCOMES]
    rows=[]
    valid = df[df.status.eq("VALID")].copy()
    if valid.empty:
        return pd.DataFrame()
    def add(name, cols, mask):
        q=valid[mask]
        n=len(q)
        if n < MIN_OUTCOMES: return
        dates=q.trade_date.nunique(); syms=q.symbol.nunique()
        if dates < MIN_DATES or syms < MIN_SYMBOLS: return
        for target in ("reached_0.5x","reached_1.0x","reached_1.5x"):
            rate=float(q[target].mean())
            hold=float(q.path_class.eq("MOVE_HOLDING").mean())
            clean=float(q.path_class.isin(["MOVE_HOLDING"]).mean())
            rows.append({"pattern":name,"factors":" + ".join(cols),"k":len(cols),"n":n,"dates":dates,"symbols":syms,
                         "target":target,"favorable_rate":rate,"holding_rate":hold,"clean_hold_rate":clean,
                         "gate_80":bool(rate>=FINAL_RATE),"hit_zone_67_80":bool(rate>=HIT_FLOOR),
                         "retrace_rate":float(q.path_class.eq("MOVE_THEN_RETRACE").mean())})
    # Individual first.
    for c in bool_cols: add(c,[c],valid[c])
    # Bounded combinations: take the strongest 24 individual features by 1x rate,
    # then test pairs/triples/quads only. This prevents millions of combinations.
    scores=[]
    for c in bool_cols:
        q=valid[valid[c]]
        if len(q)>=MIN_OUTCOMES and q.trade_date.nunique()>=MIN_DATES and q.symbol.nunique()>=MIN_SYMBOLS:
            scores.append((float(q["reached_1.0x"].mean()),c))
    top=[c for _,c in sorted(scores, reverse=True)[:24]]
    from itertools import combinations
    for k in range(2,max_k+1):
        for cols in combinations(top,k):
            mask=valid[list(cols)].all(axis=1)
            add(" & ".join(cols),list(cols),mask)
    if not rows: return pd.DataFrame()
    out=pd.DataFrame(rows)
    return out.sort_values(["favorable_rate","n"],ascending=[False,False]).reset_index(drop=True)


def run_one_window(df, pidx, out, window_min, max_k):
    anchors = orb_anchors(pidx, window_min)
    anchors.to_csv(out / f"orb_anchors_{window_min}m.csv", index=False)
    print(f"ORB_ANCHORS_{window_min}M: {len(anchors)}")
    if anchors.empty:
        return pd.DataFrame(), pd.DataFrame()
    state = latest_state(df, anchors)
    feat = add_features(state)
    outcomes = attach_outcomes(feat, pidx)
    outcomes.to_csv(out / f"orb_evidence_outcomes_{window_min}m.csv", index=False)
    print(f"OUTCOME_STATUS_{window_min}M:", json.dumps(outcomes.status.value_counts(dropna=False).to_dict(), default=str))
    patterns = discover_patterns(outcomes, max_k)
    if not patterns.empty:
        patterns.insert(0, "orb_minutes", window_min)
    patterns.to_csv(out / f"pattern_candidates_{window_min}m.csv", index=False)
    return outcomes, patterns


def enrich_hit_study(patterns: pd.DataFrame) -> pd.DataFrame:
    if patterns.empty:
        return patterns
    p = patterns.copy()
    p["quality"] = np.where((p["n"] >= 60) & (p["dates"] >= 8) & (p["symbols"] >= 20), "HIGH_SAMPLE",
                     np.where((p["n"] >= 40) & (p["dates"] >= 5) & (p["symbols"] >= 15), "MEDIUM_SAMPLE", "RESEARCH_ONLY"))
    p["validation_priority"] = np.select(
        [p["favorable_rate"] >= 0.80, p["favorable_rate"] >= 0.75, p["favorable_rate"] >= 0.70, p["favorable_rate"] >= 0.67],
        ["80_PLUS", "75_79", "70_74", "67_69"], default="BELOW_67")
    return p.sort_values(["favorable_rate", "n", "dates", "symbols"], ascending=[False, False, False, False]).reset_index(drop=True)


def run(args):
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    cache = find_cache(root)
    if not cache:
        print("CACHE_NOT_FOUND: smart engine refuses a full XLSX rescan in resource-saving mode")
        print("ACTION: run the existing canonical builder first, then rerun this script")
        return 2
    print(f"EVIDENCE_CACHE_FOUND: {cache}")
    df = load_canonical(cache)
    print(f"CANONICAL_ROWS: {len(df)}")
    print(f"SYMBOLS: {df.symbol.nunique()} | DATES: {df.trade_date.nunique()} | TIMESTAMPED: {df.timestamp.notna().sum()}")
    cand = price_stream_candidates(df)
    cand.to_csv(out / "price_stream_candidates.csv", index=False)
    print(f"PRICE_STREAM_CANDIDATES: {len(cand)}")
    stream, meta = choose_price_stream(df)
    if args.mode == "audit":
        print(f"PRICE_STREAM_ROWS: {len(stream)}")
        print("SELECTED_PRICE_STREAM:", json.dumps({k:v for k,v in meta.items() if k!='candidates'}, default=str))
        print("REPLAY_AUDIT:", json.dumps(replay_diagnostic(df, build_price_index(stream)), default=str))
        pd.DataFrame(meta.get("candidates", [])).to_csv(out / "price_stream_selection.csv", index=False)
        return 0
    if stream.empty:
        print("REPLAY_GATE: FAIL_NO_PRICE_STREAM")
        print("PATTERN_MINING_SKIPPED")
        return 3
    pidx = build_price_index(stream)
    audit = replay_diagnostic(df, pidx)
    print("REPLAY_AUDIT:", json.dumps(audit))
    if audit["keys_with_evidence_before_price_end"] == 0:
        print("REPLAY_GATE: FAIL_NO_FORWARD_PRICE_LINK")
        print("PATTERN_MINING_SKIPPED")
        return 4

    # Smart second pass: run multiple ORB windows against the SAME cached timeline.
    all_patterns=[]
    all_outcomes=[]
    for window in args.orb_windows:
        outcomes, patterns = run_one_window(df, pidx, out, window, args.max_k)
        if not outcomes.empty:
            outcomes.insert(0, "orb_minutes", window)
            all_outcomes.append(outcomes)
        if not patterns.empty:
            all_patterns.append(patterns)
    if all_outcomes:
        pd.concat(all_outcomes, ignore_index=True).to_csv(out / "multi_window_outcomes.csv", index=False)
    combined = enrich_hit_study(pd.concat(all_patterns, ignore_index=True) if all_patterns else pd.DataFrame())
    combined.to_csv(out / "multi_window_pattern_candidates.csv", index=False)
    hits = combined[combined.favorable_rate >= HIT_FLOOR] if not combined.empty else combined
    accepted = combined[combined.gate_80] if not combined.empty else combined
    print(f"MULTI_WINDOW_PATTERNS: {len(combined)}")
    print(f"80_PERCENT_CANDIDATES: {len(accepted)}")
    print(f"67_TO_80_PERCENT_CANDIDATES: {len(hits)}")
    if not hits.empty:
        hits.head(50).to_csv(out / "hit_zone_67_plus_top50.csv", index=False)
        print("TOP_HIT_ZONE:")
        print(hits.head(20).to_string(index=False))
    else:
        print("HIT_ZONE_RESULT: no >=67% pattern under current feature/outcome definitions")
    print(f"ELAPSED_SEC: {time.time()-t:.1f}")
    return 0

def self_test():
    # Synthetic chronology test: evidence at 10:05 must only see price at 10:10+.
    ts=pd.to_datetime(["2026-09-01 09:15","2026-09-01 09:20","2026-09-01 09:30","2026-09-01 09:35","2026-09-01 09:40"])
    p=pd.DataFrame({"symbol":["AAA"]*5,"trade_date":[pd.Timestamp("2026-09-01").date()]*5,"timestamp":ts,
                    "open":[100,101,101,103,104],"high":[101,102,103,105,106],"low":[99,100,100,102,103],"close":[100.5,101.5,102.5,104.5,105.5],"family":["PRICE"]*5})
    e=pd.DataFrame({"symbol":["AAA"],"trade_date":[pd.Timestamp("2026-09-01").date()],"timestamp":[pd.Timestamp("2026-09-01 09:35")],"family":["FUTURES"],"fut_num":[1200],"fut_pct":[2.1],"fut_state":["LB"]})
    idx=build_price_index(p)
    assert replay_diagnostic(e,idx)["keys_with_evidence_before_price_end"] == 1
    a=orb_anchors(idx,15)
    assert not a.empty
    s=latest_state(e,a); assert len(s)==1
    f=add_features(s); assert bool(f.fut_gt1000.iloc[0])
    o=attach_outcomes(f,idx); assert o.status.iloc[0]=="VALID"
    print("SELF_TEST_PASS")


def main():
    ap=argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--root",default=r"E:\\NSE_Daily_Analysis")
    ap.add_argument("--out",default=None)
    ap.add_argument("--mode",choices=["audit","discover","self-test"],default="audit")
    ap.add_argument("--orb-windows", nargs="+", type=int, default=[5,10,15], help="ORB windows to test in one cached pass")
    ap.add_argument("--orb-minutes",type=int,choices=[5,10,15,20],default=15)
    ap.add_argument("--max-k",type=int,choices=[2,3,4],default=3)
    a=ap.parse_args()
    if a.mode=="self-test": return self_test()
    if a.out is None:
        a.out=str(Path(a.root)/"SDL"/"Sector_Analysis"/".sector_intelligence"/"smart_replay_hit_discovery")
    return run(a)

if __name__=="__main__":
    sys.exit(main())
