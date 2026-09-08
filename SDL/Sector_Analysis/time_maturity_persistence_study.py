#!/usr/bin/env python3
"""Cache-only time-maturity + persistence study for NTIS SDL.

Uses existing Smart Replay Hit Discovery CSV outputs only. It does not scan raw
XLSX/PDF/image sources and does not modify the dashboard or production logic.

The study evaluates the same replay anchors at clock-time maturity cutoffs
(09:30, 09:45, 10:00, 10:15) and tests whether evidence available by that time
is associated with later favorable/holding outcomes. It also compares 5/10/15m
ORB windows and preserves the distinction between initial excursion and holding.

This is descriptive historical research. It does not accept, optimize, or
promote a trading rule; the project's >=80% validation gate remains unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
DISCOVERY = "smart_replay_hit_discovery"
OUT = "time_maturity_persistence_study"
PATTERN_NAMES = ("pattern_candidates_5m.csv", "pattern_candidates_10m.csv", "pattern_candidates_15m.csv")
OUTCOME_NAMES = ("orb_evidence_outcomes_5m.csv", "orb_evidence_outcomes_10m.csv", "orb_evidence_outcomes_15m.csv")
MATURITY = ("09:30", "09:45", "10:00", "10:15")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def find_discovery(root: Path) -> Path:
    p = root / DISCOVERY
    if p.is_dir():
        return p
    hits = list(root.rglob(DISCOVERY)) if root.exists() else []
    if hits:
        return hits[0]
    raise FileNotFoundError(f"Discovery directory not found under {root}")


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def truth(v) -> bool:
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def parse_time_series(df: pd.DataFrame) -> pd.Series:
    for col in ("timestamp", "observation_timestamp", "event_timestamp", "datetime", "date_time"):
        if col in df.columns:
            return pd.to_datetime(df[col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index)


def load_outcomes(discovery: Path) -> dict[int, pd.DataFrame]:
    out: dict[int, pd.DataFrame] = {}
    for minutes in (5, 10, 15):
        p = discovery / f"orb_evidence_outcomes_{minutes}m.csv"
        if not p.exists():
            continue
        df = read_csv(p)
        df["__timestamp"] = parse_time_series(df)
        if "trade_date" in df.columns:
            df["__trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        else:
            df["__trade_date"] = df["__timestamp"].dt.date
        out[minutes] = df
    return out


def load_patterns(discovery: Path) -> pd.DataFrame:
    frames = []
    for minutes in (5, 10, 15):
        p = discovery / f"pattern_candidates_{minutes}m.csv"
        if not p.exists():
            continue
        df = read_csv(p)
        if df.empty:
            continue
        df["orb_minutes"] = minutes
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No pattern candidate CSVs found under {discovery}")
    allp = pd.concat(frames, ignore_index=True)
    allp["favorable_rate_num"] = num(allp, "favorable_rate")
    allp["holding_rate_num"] = num(allp, "holding_rate")
    allp["n_num"] = num(allp, "n")
    allp["dates_num"] = num(allp, "dates")
    allp["symbols_num"] = num(allp, "symbols")
    allp = allp.drop_duplicates(subset=["orb_minutes", "pattern", "target"], keep="first")
    return allp


def factors_of(row: pd.Series) -> list[str]:
    text = row.get("factors", row.get("pattern", ""))
    if pd.isna(text):
        return []
    return [x.strip() for x in str(text).split("&") if x.strip()]


def pattern_mask(df: pd.DataFrame, row: pd.Series) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    factors = factors_of(row)
    for factor in factors:
        if factor not in df.columns:
            return pd.Series(False, index=df.index)
        mask &= df[factor].map(truth)
    return mask


def choose_baseline_patterns(patterns: pd.DataFrame, top_n: int, min_rate: float) -> pd.DataFrame:
    # Study only existing research candidates. Prefer >=60% and retain a broad
    # enough set to compare maturity effects without another discovery pass.
    p = patterns[patterns["favorable_rate_num"] >= min_rate].copy()
    p = p.sort_values(["favorable_rate_num", "holding_rate_num", "n_num"], ascending=[False, False, False])
    return p.head(top_n).copy()


def maturity_stats(df: pd.DataFrame, cutoff: str) -> dict:
    if "__timestamp" not in df.columns or df["__timestamp"].isna().all():
        return {"status": "NO_TIMESTAMP"}
    hh, mm = map(int, cutoff.split(":"))
    clock = df["__timestamp"].dt.hour * 60 + df["__timestamp"].dt.minute
    c = hh * 60 + mm
    d = df.loc[clock <= c]
    result = {"status": "OK", "rows_available_by_cutoff": int(len(d))}
    for col in ("favorable", "holding", "clean_hold", "retrace"):
        result[col + "_rate"] = float(num(d, col).mean()) if col in d.columns and len(d) else None
    return result


def summarize_subset(sub: pd.DataFrame) -> dict:
    r = {"n": int(len(sub))}
    for col in ("favorable", "holding", "clean_hold", "retrace"):
        r[col + "_rate"] = float(num(sub, col).mean()) if col in sub.columns and len(sub) else None
    for col, name in (("favorable_pct", "mean_favorable_pct"), ("adverse_pct", "mean_adverse_pct"), ("final_pct", "mean_final_pct"), ("mfe_pct", "mean_mfe_pct"), ("mae_pct", "mean_mae_pct")):
        r[name] = float(num(sub, col).mean()) if col in sub.columns and len(sub) else None
    if "path_class" in sub.columns and len(sub):
        vc = sub["path_class"].fillna("UNKNOWN").astype(str).value_counts()
        for k, v in vc.items():
            r["path_" + str(k).lower() + "_n"] = int(v)
    return r


def run(root: Path, top_n: int, min_rate: float) -> Path:
    discovery = find_discovery(root)
    outdir = root / OUT
    outdir.mkdir(parents=True, exist_ok=True)

    patterns = load_patterns(discovery)
    outcomes = load_outcomes(discovery)
    selected = choose_baseline_patterns(patterns, top_n, min_rate)

    rows = []
    for _, pat in selected.iterrows():
        minutes = int(pat["orb_minutes"])
        df = outcomes.get(minutes)
        if df is None or df.empty:
            continue
        mask = pattern_mask(df, pat)
        matched = df.loc[mask].copy()
        if matched.empty:
            continue
        base = {
            "orb_minutes": minutes,
            "pattern": pat.get("pattern", ""),
            "factors": pat.get("factors", ""),
            "target": pat.get("target", ""),
            "reported_favorable_rate": pat.get("favorable_rate", ""),
            "reported_holding_rate": pat.get("holding_rate", ""),
            "reported_n": pat.get("n", ""),
            "reported_dates": pat.get("dates", ""),
            "reported_symbols": pat.get("symbols", ""),
            "matched_rows": len(matched),
        }
        for cutoff in MATURITY:
            # Only rows whose observation timestamp is at/before cutoff are
            # considered "mature by cutoff". Outcome columns are later replay
            # outcomes, so this remains a retrospective descriptive study.
            if matched["__timestamp"].isna().all():
                sub = matched.iloc[0:0]
            else:
                hh, mm = map(int, cutoff.split(":"))
                clock = matched["__timestamp"].dt.hour * 60 + matched["__timestamp"].dt.minute
                sub = matched.loc[clock <= hh * 60 + mm]
            s = summarize_subset(sub)
            row = dict(base)
            row["maturity_cutoff"] = cutoff
            row.update({"mature_rows": s.pop("n")})
            row.update(s)
            rows.append(row)

    maturity = pd.DataFrame(rows)
    if not maturity.empty:
        maturity["favorable_rate_change_vs_reported"] = maturity["favorable_rate"] - num(maturity, "reported_favorable_rate")
        maturity["holding_rate_change_vs_reported"] = maturity["holding_rate"] - num(maturity, "reported_holding_rate")
        maturity.to_csv(outdir / "maturity_by_pattern.csv", index=False)

    # Aggregate by clock cutoff and ORB window.
    agg_rows = []
    for (minutes, cutoff), g in maturity.groupby(["orb_minutes", "maturity_cutoff"], dropna=False) if not maturity.empty else []:
        agg_rows.append({
            "orb_minutes": int(minutes),
            "maturity_cutoff": cutoff,
            "patterns": int(len(g)),
            "total_mature_rows": int(num(g, "mature_rows").sum()),
            "mean_favorable_rate": float(num(g, "favorable_rate").mean()),
            "median_favorable_rate": float(num(g, "favorable_rate").median()),
            "mean_holding_rate": float(num(g, "holding_rate").mean()),
            "median_holding_rate": float(num(g, "holding_rate").median()),
            "mean_clean_hold_rate": float(num(g, "clean_hold_rate").mean()),
            "mean_retrace_rate": float(num(g, "retrace_rate").mean()),
        })
    agg = pd.DataFrame(agg_rows)
    agg.to_csv(outdir / "maturity_window_summary.csv", index=False)

    # Direct maturity cohorts on all replay anchors, independent of pattern.
    cohort_rows = []
    for minutes, df in sorted(outcomes.items()):
        if df.empty or df["__timestamp"].isna().all():
            continue
        for cutoff in MATURITY:
            hh, mm = map(int, cutoff.split(":"))
            clock = df["__timestamp"].dt.hour * 60 + df["__timestamp"].dt.minute
            sub = df.loc[clock <= hh * 60 + mm]
            s = summarize_subset(sub)
            cohort_rows.append({"orb_minutes": minutes, "maturity_cutoff": cutoff, **s})
    cohort = pd.DataFrame(cohort_rows)
    cohort.to_csv(outdir / "all_anchor_maturity_cohorts.csv", index=False)

    # Compact decision-oriented ranking: strongest change in holding rate while
    # retaining at least the project's descriptive 60% initial-hit research zone.
    ranked = maturity.copy()
    if not ranked.empty:
        ranked["maturity_score_hint"] = ranked["holding_rate_change_vs_reported"].fillna(-999) + 0.25 * ranked["favorable_rate_change_vs_reported"].fillna(-999)
        ranked = ranked.sort_values(["maturity_score_hint", "holding_rate", "favorable_rate"], ascending=False)
        ranked.head(100).to_csv(outdir / "maturity_persistence_top100.csv", index=False)

    summary = {
        "status": "READY",
        "cache_only": True,
        "raw_source_scan": False,
        "discovery_dir": str(discovery),
        "output_dir": str(outdir),
        "pattern_rows": int(len(patterns)),
        "patterns_analyzed": int(len(selected)),
        "min_rate": min_rate,
        "max_existing_favorable_rate": float(patterns["favorable_rate_num"].max()),
        "maturity_cutoffs": list(MATURITY),
        "orb_windows_available": sorted(int(x) for x in outcomes),
        "note": "Descriptive historical replay only. Waiting-time comparisons do not accept or optimize a strategy; >=80% remains the hard validation gate.",
    }
    (outdir / "time_maturity_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return outdir


def main() -> int:
    ap = argparse.ArgumentParser(description="Cache-only NTIS SDL time-maturity + persistence study")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--top-n", type=int, default=27)
    ap.add_argument("--min-rate", type=float, default=0.60)
    args = ap.parse_args()
    out = run(args.root, max(1, args.top_n), args.min_rate)
    print(json.dumps({"TIME_MATURITY_PERSISTENCE_STUDY": "READY", "OUTPUT": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
