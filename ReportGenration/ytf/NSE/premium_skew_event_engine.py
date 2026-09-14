#!/usr/bin/env python3
"""
Premium Skew event-state engine.

Consumes timestamped premium-skew rows with:
symbol, timestamp, fixed_atm_strike, atm_ce_premium, atm_pe_premium, bias_pct

Frozen thresholds:
  abs(Bias) >= 15 -> BROKE (immediate)
  abs(Bias) >= 20 -> BROKE (confirmed)
  abs(Bias) >= 30 -> BROKEN status

The engine emits one immediate event and one confirmed event per symbol when
the relevant crossings exist. If no confirmed crossing exists, the confirmed
event is marked NOT_CONFIRMED rather than silently fabricated.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

IMMEDIATE = 15.0
CONFIRMED = 20.0
BROKEN = 30.0

def signed_side(bias: float) -> str:
    return "CALL_SIDE" if bias > 0 else "PUT_SIDE"

def event_row(row, event, status, threshold):
    bias = float(row["bias_pct"])
    return {
        "symbol": row["symbol"],
        "timestamp": row["timestamp"],
        "fixed_atm_strike": row.get("fixed_atm_strike"),
        "atm_ce_premium": row.get("atm_ce_premium"),
        "atm_pe_premium": row.get("atm_pe_premium"),
        "bias_pct": bias,
        "side": signed_side(bias),
        "event": event,
        "status": status,
        "threshold_pct": threshold,
    }

def process(args):
    df = pd.read_csv(args.input)
    required = {"symbol", "timestamp", "bias_pct"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))

    df["bias_pct"] = pd.to_numeric(df["bias_pct"], errors="coerce")
    df = df.dropna(subset=["symbol", "timestamp", "bias_pct"]).copy()
    df["_time"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["_time"]).sort_values(["symbol", "_time"])

    output = []
    for symbol, group in df.groupby("symbol", sort=False):
        immediate = group[group["bias_pct"].abs() >= IMMEDIATE]
        if immediate.empty:
            continue
        first_immediate = immediate.iloc[0]
        output.append(event_row(first_immediate, "BROKE", "immediate", IMMEDIATE))

        # Confirmation must preserve the direction of the immediate crossing.
        direction = 1 if float(first_immediate["bias_pct"]) > 0 else -1
        confirmed = group[
            (group["bias_pct"] * direction >= CONFIRMED)
        ]
        confirmed = confirmed[confirmed["_time"] >= first_immediate["_time"]]

        if confirmed.empty:
            r = event_row(first_immediate, "BROKE", "NOT_CONFIRMED", CONFIRMED)
            output.append(r)
        else:
            first_confirmed = confirmed.iloc[0]
            status = "BROKEN" if abs(float(first_confirmed["bias_pct"])) >= BROKEN else "confirmed"
            output.append(event_row(first_confirmed, "BROKE", status, CONFIRMED))

    result = pd.DataFrame(output)
    if not result.empty:
        result = result.sort_values(["symbol", "timestamp"])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(json.dumps({
        "status": "OK",
        "input_rows": int(len(df)),
        "event_rows": int(len(result)),
        "output": str(args.output),
        "thresholds": {
            "immediate": IMMEDIATE,
            "confirmed": CONFIRMED,
            "broken": BROKEN
        }
    }, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Timestamped premium-skew CSV")
    p.add_argument("--output", required=True, help="Event CSV")
    process(p.parse_args())
