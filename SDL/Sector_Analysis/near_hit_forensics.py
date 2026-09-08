#!/usr/bin/env python3
"""Cache-only near-hit forensics for Smart Replay Hit Discovery.

Does NOT scan raw XLSX/PDF/image sources and does NOT touch the dashboard.
It analyzes the existing smart_replay_hit_discovery CSV outputs and explains
why the strongest near-hit patterns succeed/fail along their replay path.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
DISCOVERY_DIRNAME = "smart_replay_hit_discovery"
OUT_DIRNAME = "near_hit_forensics"
PATTERN_RE = re.compile(r"^pattern_candidates_(5m|10m|15m)\.csv$", re.I)
OUTCOME_RE = re.compile(r"^orb_evidence_outcomes_(5m|10m|15m)\.csv$", re.I)


def _find_dir(root: Path) -> Path:
    direct = root / DISCOVERY_DIRNAME
    if direct.is_dir():
        return direct
    matches = list(root.rglob(DISCOVERY_DIRNAME)) if root.exists() else []
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Discovery output directory not found under: {root}")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def _bool_value(v) -> bool:
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def _parse_factors(value: str) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    # Discovery patterns are conjunctions. Accept factors column first, then pattern.
    return [x.strip() for x in text.split("&") if x.strip()]


def _mask_for_pattern(outcomes: pd.DataFrame, factors_text: str) -> tuple[pd.Series, list[str], list[str]]:
    factors = _parse_factors(factors_text)
    mask = pd.Series(True, index=outcomes.index)
    used, missing = [], []
    for factor in factors:
        if factor not in outcomes.columns:
            missing.append(factor)
            continue
        mask &= outcomes[factor].map(_bool_value)
        used.append(factor)
    # A pattern with missing factors is unsafe to analyze as a complete match.
    if missing:
        mask &= False
    return mask, used, missing


def _path_summary(matched: pd.DataFrame, candidate: pd.Series) -> dict:
    row = {
        "orb_minutes": candidate.get("orb_minutes", ""),
        "target": candidate.get("target", ""),
        "pattern": candidate.get("pattern", ""),
        "n_pattern_reported": candidate.get("n", ""),
        "n_matched_reconstructed": int(len(matched)),
        "reported_favorable_rate": float(candidate.get("favorable_rate", float("nan"))),
        "reported_holding_rate": float(candidate.get("holding_rate", float("nan"))),
        "reported_clean_hold_rate": float(candidate.get("clean_hold_rate", float("nan"))),
        "reported_retrace_rate": float(candidate.get("retrace_rate", float("nan"))),
    }
    for col, outname in [
        ("favorable_pct", "mean_favorable_pct"),
        ("adverse_pct", "mean_adverse_pct"),
        ("final_pct", "mean_final_pct"),
        ("mfe_pct", "mean_mfe_pct"),
        ("mae_pct", "mean_mae_pct"),
    ]:
        if col in matched.columns:
            row[outname] = float(_num(matched, col).mean())
    if "path_class" in matched.columns:
        counts = matched["path_class"].fillna("UNKNOWN").astype(str).value_counts()
        total = max(len(matched), 1)
        for key in [
            "MOVE_HOLDING", "MOVE_THEN_RETRACE", "DIRECTION_ONLY_CONTINUATION",
            "DIRECTION_ONLY_OPPOSITE", "NO_MATERIAL_MOVE", "UNKNOWN_DIRECTION",
        ]:
            row[f"path_{key.lower()}_n"] = int(counts.get(key, 0))
            row[f"path_{key.lower()}_rate"] = float(counts.get(key, 0) / total)
        row["path_other_n"] = int(sum(v for k, v in counts.items() if k not in {
            "MOVE_HOLDING", "MOVE_THEN_RETRACE", "DIRECTION_ONLY_CONTINUATION",
            "DIRECTION_ONLY_OPPOSITE", "NO_MATERIAL_MOVE", "UNKNOWN_DIRECTION"}))
    if "status" in matched.columns:
        row["status_no_follow_up_n"] = int((matched["status"].astype(str).str.upper() == "NO_FOLLOW_UP").sum())
    if "direction" in matched.columns:
        row["direction_up_n"] = int((matched["direction"].astype(str).str.upper() == "UP").sum())
        row["direction_down_n"] = int((matched["direction"].astype(str).str.upper() == "DOWN").sum())
    if "trade_date" in matched.columns:
        row["dates_n_reconstructed"] = int(matched["trade_date"].nunique())
    if "symbol" in matched.columns:
        row["symbols_n_reconstructed"] = int(matched["symbol"].nunique())
    return row


def _load_patterns(discovery: Path) -> pd.DataFrame:
    frames = []
    for p in sorted(discovery.iterdir()):
        if not p.is_file() or not PATTERN_RE.match(p.name):
            continue
        df = _read_csv(p)
        if df.empty:
            continue
        m = PATTERN_RE.match(p.name)
        df["orb_minutes"] = int(m.group(1)[:-1])
        df["source_pattern_file"] = str(p)
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No pattern_candidates_{{5m,10m,15m}}.csv found in {discovery}")
    allp = pd.concat(frames, ignore_index=True)
    allp["favorable_rate_num"] = _num(allp, "favorable_rate")
    allp["n_num"] = _num(allp, "n")
    allp["dates_num"] = _num(allp, "dates")
    allp["symbols_num"] = _num(allp, "symbols")
    allp = allp.drop_duplicates(subset=["orb_minutes", "pattern", "target"], keep="first")
    return allp


def _load_outcomes(discovery: Path) -> dict[int, pd.DataFrame]:
    result = {}
    for p in sorted(discovery.iterdir()):
        m = OUTCOME_RE.match(p.name) if p.is_file() else None
        if not m:
            continue
        minutes = int(m.group(1)[:-1])
        result[minutes] = _read_csv(p)
    return result


def run(root: Path, top_n: int, min_rate: float, max_rate: float) -> Path:
    discovery = _find_dir(root)
    outdir = root / OUT_DIRNAME
    outdir.mkdir(parents=True, exist_ok=True)

    patterns = _load_patterns(discovery)
    outcomes = _load_outcomes(discovery)

    # Near-hit = strongest currently observed candidates, including all >= min_rate.
    # max_rate is only a classification ceiling; >=80% remains separately visible.
    selected = patterns[patterns["favorable_rate_num"] >= min_rate].copy()
    selected = selected.sort_values(["favorable_rate_num", "n_num"], ascending=[False, False]).head(top_n)

    band = pd.Series("BELOW_60", index=patterns.index)
    r = patterns["favorable_rate_num"]
    band.loc[r >= 0.60] = "60_TO_67"
    band.loc[r >= 0.67] = "67_TO_70"
    band.loc[r >= 0.70] = "70_TO_75"
    band.loc[r >= 0.75] = "75_TO_80"
    band.loc[r >= 0.80] = "80_PLUS"
    patterns["rate_band"] = band
    patterns.to_csv(outdir / "all_pattern_rate_bands.csv", index=False)
    selected.to_csv(outdir / "near_hit_ranked.csv", index=False)

    decomposition = []
    feature_rows = []
    for _, cand in selected.iterrows():
        minutes = int(cand["orb_minutes"])
        df = outcomes.get(minutes)
        if df is None:
            continue
        factor_text = cand.get("factors", cand.get("pattern", ""))
        mask, used, missing = _mask_for_pattern(df, factor_text)
        matched = df.loc[mask].copy()
        item = _path_summary(matched, cand)
        item["factors_used"] = " & ".join(used)
        item["factors_missing"] = " & ".join(missing)
        decomposition.append(item)

        # Lightweight single-factor comparison within the matched population.
        # This is descriptive only; it does not declare an optimized rule.
        if len(matched) >= 1:
            for factor in used:
                if factor not in matched.columns:
                    continue
                for val in [True, False]:
                    sub = matched[matched[factor].map(_bool_value) == val]
                    if len(sub) == 0:
                        continue
                    rates = {}
                    for col in ["favorable", "holding", "clean_hold", "retrace"]:
                        if col in sub.columns:
                            rates[col + "_rate"] = float(_num(sub, col).mean())
                        else:
                            rates[col + "_rate"] = None
                    feature_rows.append({
                        "orb_minutes": minutes,
                        "parent_pattern": cand.get("pattern", ""),
                        "target": cand.get("target", ""),
                        "factor": factor,
                        "factor_value": val,
                        "n": len(sub),
                        "dates": sub["trade_date"].nunique() if "trade_date" in sub.columns else None,
                        "symbols": sub["symbol"].nunique() if "symbol" in sub.columns else None,
                        **rates,
                    })

    decomp = pd.DataFrame(decomposition)
    if not decomp.empty:
        decomp = decomp.sort_values(["reported_favorable_rate", "n_matched_reconstructed"], ascending=[False, False])
    decomp.to_csv(outdir / "near_hit_path_decomposition.csv", index=False)
    pd.DataFrame(feature_rows).to_csv(outdir / "near_hit_feature_descriptives.csv", index=False)

    summary = {
        "status": "READY",
        "discovery_dir": str(discovery),
        "output_dir": str(outdir),
        "pattern_rows": int(len(patterns)),
        "pattern_rows_ge_min_rate": int((patterns["favorable_rate_num"] >= min_rate).sum()),
        "max_favorable_rate": float(patterns["favorable_rate_num"].max()),
        "count_60_to_67": int((band == "60_TO_67").sum()),
        "count_67_to_70": int((band == "67_TO_70").sum()),
        "count_70_to_75": int((band == "70_TO_75").sum()),
        "count_75_to_80": int((band == "75_TO_80").sum()),
        "count_80_plus": int((band == "80_PLUS").sum()),
        "top_n_analyzed": int(len(selected)),
        "decomposition_rows": int(len(decomp)),
        "cache_only": True,
        "raw_source_scan": False,
        "note": "Rates are descriptive historical replay evidence. No strategy is accepted or optimized by this tool.",
    }
    (outdir / "near_hit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return outdir


def main() -> int:
    ap = argparse.ArgumentParser(description="Cache-only near-hit forensics for NTIS SDL Smart Replay outputs")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=".sector_intelligence root")
    ap.add_argument("--top-n", type=int, default=100, help="maximum candidates to decompose")
    ap.add_argument("--min-rate", type=float, default=0.60, help="minimum favorable rate to inspect")
    ap.add_argument("--max-rate", type=float, default=0.80, help="reserved reporting ceiling; >=80 remains separate")
    args = ap.parse_args()
    out = run(args.root, max(1, args.top_n), args.min_rate, args.max_rate)
    print(json.dumps({"NEAR_HIT_FORENSICS": "READY", "OUTPUT": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
