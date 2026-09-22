from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "00_BASELINE" / "chronological_validation_corrected.csv"
OUT = ROOT / "00_BASELINE"
OUT.mkdir(parents=True, exist_ok=True)

REQUIRED = ["holdout_rate", "holdout_n", "holdout_dates", "holdout_symbols"]
META = {
    "candidate_id", "pattern_id", "rank", "score",
    "holdout_rate", "holdout_n", "holdout_dates", "holdout_symbols",
    "train_rate", "train_n", "train_dates", "train_symbols",
    "target", "reached_0_5x"
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def json_value(v):
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v

def main():
    if not BASELINE.exists():
        raise FileNotFoundError(f"Missing W73 baseline: {BASELINE}")

    source_hash = sha256(BASELINE)
    df = pd.read_csv(BASELINE)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise RuntimeError(f"Baseline validation is missing required columns: {missing}")

    work = df.copy()
    for c in REQUIRED:
        work[c] = pd.to_numeric(work[c], errors="coerce")

    invalid_rate = work["holdout_rate"].dropna().loc[
        ~work["holdout_rate"].dropna().between(0, 1, inclusive="both")
    ]
    if len(invalid_rate):
        raise RuntimeError("Invalid holdout_rate outside [0,1] found.")

    robust = work.dropna(subset=REQUIRED)
    robust = robust[
        (robust["holdout_n"] >= 30)
        & (robust["holdout_dates"] >= 3)
        & (robust["holdout_symbols"] >= 10)
    ].copy()

    if robust.empty:
        raise RuntimeError("No candidate satisfies the frozen robustness gate.")

    max_rate = robust["holdout_rate"].max()
    winners = robust[robust["holdout_rate"] == max_rate].copy()

    # If several candidates tie, preserve every tied candidate and identify the
    # first deterministically by original row order. Do not invent a ranking.
    winner = winners.iloc[0]

    candidate_id = str(
        winner.get("candidate_id",
        winner.get("pattern_id", f"ROW_{winner.name}"))
    )

    conditions = {}
    for c in robust.columns:
        if c in META:
            continue
        v = winner[c]
        if pd.notna(v):
            conditions[c] = json_value(v)

    baseline = {
        "schema_version": "W73_STRATEGY_BASELINE_V1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(BASELINE),
        "source_sha256": source_hash,
        "validation_rows": int(len(df)),
        "robust_candidates": int(len(robust)),
        "max_holdout_rate": float(max_rate),
        "max_holdout_rate_pct": float(max_rate * 100),
        "holdout_n": int(winner["holdout_n"]),
        "holdout_dates": int(winner["holdout_dates"]),
        "holdout_symbols": int(winner["holdout_symbols"]),
        "tied_max_candidates": int(len(winners)),
        "candidate_id": candidate_id,
        "conditions": conditions,
        "frozen_gate": {
            "holdout_rate_threshold": 0.80,
            "holdout_n_min": 30,
            "holdout_dates_min": 3,
            "holdout_symbols_min": 10
        },
        "status": "FROZEN_CANDIDATE_EXTRACTION_ONLY"
    }

    (OUT / "strategy_baseline_v1.json").write_text(
        json.dumps(baseline, indent=2, default=str),
        encoding="utf-8"
    )

    winners.to_csv(
        OUT / "maximum_rate_tied_candidates.csv",
        index=False
    )

    summary = [
        "NTIS SDL INTRADAY W73 — BASELINE EXTRACTION",
        "=" * 55,
        f"Source rows: {len(df)}",
        f"Robust candidates: {len(robust)}",
        f"Maximum robust holdout rate: {max_rate * 100:.3f}%",
        f"Maximum holdout n: {int(winner['holdout_n'])}",
        f"Maximum holdout dates: {int(winner['holdout_dates'])}",
        f"Maximum holdout symbols: {int(winner['holdout_symbols'])}",
        f"Tied maximum candidates: {len(winners)}",
        f"Selected candidate: {candidate_id}",
        f"Source SHA256: {source_hash}",
        "",
        "IMPORTANT:",
        "This step freezes the historical candidate definition only.",
        "It does not claim live probability or future performance.",
        "The next gate is independent reproduction using W73-owned code.",
    ]
    (OUT / "BASELINE_EXTRACTION_RESULT.txt").write_text(
        "\n".join(summary), encoding="utf-8"
    )

    print("STATUS COMPLETE")
    print(f"SOURCE_ROWS={len(df)}")
    print(f"ROBUST_CANDIDATES={len(robust)}")
    print(f"MAX_RATE_PCT={max_rate * 100:.3f}")
    print(f"MAX_N={int(winner['holdout_n'])}")
    print(f"MAX_DATES={int(winner['holdout_dates'])}")
    print(f"MAX_SYMBOLS={int(winner['holdout_symbols'])}")
    print(f"TIED_MAX={len(winners)}")
    print(f"CANDIDATE={candidate_id}")
    print(f"SHA256={source_hash}")
    print(f"OUTPUT={OUT / 'strategy_baseline_v1.json'}")

if __name__ == "__main__":
    main()
