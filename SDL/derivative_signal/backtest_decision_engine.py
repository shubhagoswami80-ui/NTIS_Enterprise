"""
NTIS SDL — Decision Engine Backtest / Strategy Evaluation
===========================================================

Purpose
-------
Turn your historical 5-minute intraday archive (Daywise snapshots with
futures buildup, PE-CE OI, IV, volume, S/R, etc.) into an honest,
bias-free measurement of how well the EXISTING decision engine performs.

This script does NOT invent a new decision/trading rule. It reuses the
same frozen pipeline that production already runs:

    _process_snapshot()          -> build_signal() + enrich_decision()
    _rank()                      -> the same qualification/candidate
                                     filter used by the live dashboard
    _retracement_context()       -> the same frozen retracement/re-entry
                                     calculation (broken S/R, 15m 20-EMA,
                                     session VWAP)
    _break_quality_diagnostic()  -> the same frozen "is this break
                                     actually holding" data-strength read

Default alert logic (--entry-mode retracement-reentry)
-------------------------------------------------------
An alert only fires once, in order:

  1. The stock has already passed the FULL existing decision gate
     (present in _rank()'s output — price gate, direction, evidence).
  2. A primary structural break has occurred in that direction
     (resistance broken for bullish / support broken for bearish).
  3. Price retraces and actually touches one of the three retest
     references — the broken level itself, today's 15m 20-EMA, or
     today's session VWAP — while the primary direction has NOT
     reversed. This is the point _retracement_context() reports status
     "REENTRY ALERT".
  4. The alert is tagged with a data-strength verdict from
     _break_quality_diagnostic() (e.g. SUSTAINED / RECLAIMED vs
     WEAKENED-RETESTED) describing whether the original break looks
     like it's holding or already fading.

Only the first re-entry per symbol per day is scored (one-shot, same
rule production uses). Use --entry-mode first-alert to instead score
the original gate-passing moment with no retracement requirement, for
comparison, or every-qualified-snapshot for the naive/inflated count.

What this script is NOT
------------------------
- It is not a trading recommendation engine.
- It does not alter decision_evidence.py, signal_engine.py, dashboard.py,
  gate thresholds, or ranking. It only calls them.
- It does not manage risk (stops/targets) for you; forward returns are
  raw price moves, not accounted for slippage/costs. Use the results as
  a research signal, not a final answer.

Usage
-----
Run from inside the SDL/derivative_signal folder (or add it to
PYTHONPATH) so the existing modules are importable:

    python backtest_decision_engine.py --root "D:\\...\\August26" \
        --horizons 3 6 12 24 --out-dir ./backtest_output

    # Only specific symbols, only specific dates, count every snapshot
    python backtest_decision_engine.py --root "D:\\...\\August26" \
        --symbols RELIANCE TCS INFY \
        --dates 2026-08-18 2026-08-19 2026-08-20 \
        --entry-mode every-qualified-snapshot

Outputs (written to --out-dir)
-------------------------------
- backtest_trades.csv    one row per scored alert, with forward returns
- backtest_summary.csv   win-rate / mean return / expectancy by
                          decision_state and by score bucket
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# dashboard.py needs BOTH of these on sys.path: the SDL root (for
# `from config import ...`) and this derivative_signal folder (for its
# own sibling modules like decision_evidence, storage, etc.). The normal
# `streamlit run` launch gets this for free because it's started from the
# SDL root; running this script directly from either folder would
# otherwise fail with ModuleNotFoundError, so add both explicitly.
_THIS_DIR = Path(__file__).resolve().parent
_SDL_ROOT = _THIS_DIR.parent
for _p in (_THIS_DIR, _SDL_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard import (
    _discover_sources,
    _available_trading_dates,
    _first_range_from_path,
    _process_snapshot,
    _snapshot_rows,
    _read,
    _rank,
    _source_key,
    _attach_snapshot_metadata,
    _retracement_context,
    _break_quality_diagnostic,
    parse_observation_timestamp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _entry_price(row: dict[str, Any]) -> float | None:
    for key in ("reference_price", "Close", "close", "CMP", "cmp", "Price", "price"):
        value = _num(row.get(key))
        if value is not None and value > 0:
            return value
    return None


# ---------------------------------------------------------------------------
# Single-day replay
# ---------------------------------------------------------------------------

def replay_day(
    root: Path,
    trading_date: str,
    horizons: list[int],
    symbols_filter: set[str] | None,
    entry_mode: str,
) -> tuple[pd.DataFrame, list[float]]:
    """Replay one trading day through the existing frozen engine.

    Returns (trades_df, snapshot_gap_seconds) where snapshot_gap_seconds
    is used only to report the actual observed snapshot spacing, since
    "5 minutes" is nominal and real files may arrive irregularly.
    """
    sources = _discover_sources(trading_date, root)
    if not sources:
        return pd.DataFrame(), []

    first_range = _first_range_from_path(sources[0], trading_date)
    previous: dict[str, dict] = {}
    all_rows: list[dict[str, Any]] = []
    first_seen: set[str] = set()
    reentry_seen: set[str] = set()
    timestamps: list[pd.Timestamp] = []
    trade_records: list[dict[str, Any]] = []

    # Only needed for retracement-reentry mode: the FULL (unfiltered)
    # per-snapshot engine output, keyed by source file, exactly as
    # dashboard.py's _symbol_snapshot_history()/_retracement_context()
    # expect it. Built incrementally so a symbol's retracement check at
    # snapshot N only ever sees snapshots <= N (no future leakage).
    snapshot_history: dict[str, pd.DataFrame] = {}

    for seq, path in enumerate(sources, start=1):
        if seq == 1:
            # BASE snapshot only establishes the opening reference; it is
            # never a decision-bearing row (same rule the dashboard uses).
            previous = _snapshot_rows(_read(path))
            continue

        result = _process_snapshot(path, trading_date, previous, first_range)
        if result.empty:
            previous = _snapshot_rows(_read(path))
            continue

        timestamp = parse_observation_timestamp(path)
        timestamps.append(pd.Timestamp(timestamp))

        result = result.copy()
        result["_seq"] = seq
        result["_timestamp"] = timestamp

        if entry_mode == "retracement-reentry":
            # _retracement_context() reads source_timestamp/observation_timestamp
            # off each row; attach them exactly as the dashboard does before
            # this frame becomes part of the point-in-time history.
            result = _attach_snapshot_metadata(result, path)
            snapshot_history[_source_key(path)] = result

        ranked = _rank(result)

        for row in result.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            if symbols_filter and symbol not in symbols_filter:
                continue

            # Keep every processed row (all symbols) so forward-return
            # lookups by (symbol, seq) work regardless of qualification.
            all_rows.append(row)

        if entry_mode in ("first-alert", "every-qualified-snapshot"):
            for _, row in ranked.iterrows():
                symbol = str(row.get("symbol", "")).strip().upper()
                if symbols_filter and symbol not in symbols_filter:
                    continue
                if entry_mode == "first-alert" and symbol in first_seen:
                    continue
                first_seen.add(symbol)

                entry_price = _entry_price(row.to_dict())
                if entry_price is None:
                    continue

                trade_records.append(
                    {
                        "trading_date": trading_date,
                        "time": pd.Timestamp(timestamp).strftime("%H:%M:%S"),
                        "symbol": symbol,
                        "seq": seq,
                        "alert_type": "ORIGINAL_GATE",
                        "direction": str(
                            row.get("decision_direction", "NEUTRAL")
                        ).upper(),
                        "decision_state": row.get("decision_state", ""),
                        "decision_score": row.get("decision_score", 0),
                        "decision_strength": row.get("decision_strength", ""),
                        "confirmation_count": row.get("confirmation_count", 0),
                        "conflict_count": row.get("conflict_count", 0),
                        "sr_status": row.get("sr_status", ""),
                        "price_change_pct_at_entry": row.get("price_change_pct"),
                        "entry_price": entry_price,
                    }
                )

        elif entry_mode == "retracement-reentry":
            # Only rows that already passed the FULL existing decision gate
            # (_rank()) are eligible. This does not re-derive or loosen the
            # gate; it only decides, among already-qualified stocks, whether
            # a retracement re-entry has actually occurred yet.
            for _, row in ranked.iterrows():
                symbol = str(row.get("symbol", "")).strip().upper()
                if symbols_filter and symbol not in symbols_filter:
                    continue
                if symbol in reentry_seen:
                    continue  # one-shot per symbol per day, same as production

                # Frozen retracement calculation: checks broken S/R still
                # intact in direction, then tests price against whichever
                # of {broken S/R, 15m 20-EMA, session VWAP} is the nearest
                # valid retest reference. Only sees snapshots <= this one.
                ctx = _retracement_context(row, snapshot_history)
                if str(ctx.get("status", "")).upper() != "REENTRY ALERT":
                    continue

                reentry_seen.add(symbol)
                entry_price = _entry_price(row.to_dict())
                if entry_price is None:
                    continue

                # "Data strength" verdict on whether the original break is
                # holding (genuine breakout continuation) or already
                # weakening (this retest behaves like a fade), from the
                # same frozen diagnostic the dashboard shows in its audit.
                quality = _break_quality_diagnostic(row, snapshot_history)

                break_ts = ctx.get("break_timestamp")
                trade_records.append(
                    {
                        "trading_date": trading_date,
                        "time": pd.Timestamp(timestamp).strftime("%H:%M:%S"),
                        "symbol": symbol,
                        "seq": seq,
                        "alert_type": "RETRACEMENT_REENTRY",
                        "direction": str(
                            row.get("decision_direction", "NEUTRAL")
                        ).upper(),
                        "decision_state": row.get("decision_state", ""),
                        "decision_score": row.get("decision_score", 0),
                        "decision_strength": row.get("decision_strength", ""),
                        "confirmation_count": row.get("confirmation_count", 0),
                        "conflict_count": row.get("conflict_count", 0),
                        "sr_status": row.get("sr_status", ""),
                        "price_change_pct_at_entry": row.get("price_change_pct"),
                        "entry_price": entry_price,
                        "retest_reference": ctx.get("entry_name"),
                        "retest_level": ctx.get("entry_level"),
                        "break_origin": ctx.get("break_origin", ""),
                        "break_time": (
                            pd.Timestamp(break_ts).strftime("%H:%M:%S")
                            if break_ts is not None
                            else "—"
                        ),
                        "break_quality_score": quality.get("quality"),
                        "break_quality_label": quality.get("quality_label"),
                        "sustain_label": quality.get("sustain_label"),
                        "alignment": quality.get("alignment"),
                    }
                )

        previous = _snapshot_rows(_read(path))

    if not trade_records:
        return pd.DataFrame(), []

    rows_by_key = {
        (str(r.get("symbol", "")).strip().upper(), r["_seq"]): r
        for r in all_rows
    }

    trades = pd.DataFrame(trade_records)

    for h in horizons:
        col = f"fwd_ret_{h}"
        rets: list[float | None] = []
        for _, trade in trades.iterrows():
            future_row = rows_by_key.get((trade["symbol"], trade["seq"] + h))
            if future_row is None:
                rets.append(None)
                continue
            future_price = _entry_price(future_row)
            if future_price is None:
                rets.append(None)
                continue
            ret = (future_price - trade["entry_price"]) / trade["entry_price"] * 100.0
            if trade["direction"] == "BEARISH":
                ret = -ret  # positive = correct-direction move regardless of side
            rets.append(ret)
        trades[col] = rets

    gaps = [
        (b - a).total_seconds()
        for a, b in zip(timestamps, timestamps[1:])
        if (b - a).total_seconds() > 0
    ]
    return trades, gaps


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _score_bucket(score: float) -> str:
    if pd.isna(score):
        return "UNKNOWN"
    if score >= 85:
        return "85-100 (VERY STRONG)"
    if score >= 75:
        return "75-84 (STRONG)"
    if score >= 60:
        return "60-74 (MODERATE)"
    if score >= 45:
        return "45-59 (DEVELOPING)"
    return "<45 (WEAK)"


def summarize(trades: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    trades = trades.copy()
    trades["score_bucket"] = pd.to_numeric(
        trades["decision_score"], errors="coerce"
    ).map(_score_bucket)

    group_cols = ["decision_state", "score_bucket"]
    for optional_col in ("alert_type", "retest_reference", "sustain_label"):
        if optional_col in trades.columns:
            group_cols.append(optional_col)

    rows = []
    for group_col in group_cols:
        for group_value, sub in trades.groupby(group_col):
            record: dict[str, Any] = {
                "group_by": group_col,
                "group_value": group_value,
                "n_alerts": len(sub),
            }
            for h in horizons:
                col = f"fwd_ret_{h}"
                valid = sub[col].dropna()
                if valid.empty:
                    record[f"win_rate_{h}"] = None
                    record[f"mean_ret_{h}"] = None
                    record[f"expectancy_{h}"] = None
                    continue
                wins = valid[valid > 0]
                losses = valid[valid <= 0]
                win_rate = len(wins) / len(valid) * 100.0
                mean_ret = valid.mean()
                avg_win = wins.mean() if not wins.empty else 0.0
                avg_loss = losses.mean() if not losses.empty else 0.0
                expectancy = (len(wins) / len(valid)) * avg_win + (
                    len(losses) / len(valid)
                ) * avg_loss
                record[f"win_rate_{h}"] = round(win_rate, 1)
                record[f"mean_ret_{h}"] = round(mean_ret, 3)
                record[f"expectancy_{h}"] = round(expectancy, 3)
            rows.append(record)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Read-only backtest of the existing SDL decision engine. "
            "Does not modify decision_evidence.py, signal_engine.py, "
            "dashboard.py, gate thresholds, or ranking."
        )
    )
    ap.add_argument(
        "--root",
        required=True,
        help="Folder containing dated Daywise snapshot subfolders "
        "(same root you'd point the dashboard's source folder at).",
    )
    ap.add_argument(
        "--dates",
        nargs="*",
        default=None,
        help="Specific trading dates (YYYY-MM-DD) to replay. "
        "Default: every date discoverable under --root.",
    )
    ap.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Restrict to these symbols. Default: all symbols present.",
    )
    ap.add_argument(
        "--horizons",
        nargs="*",
        type=int,
        default=[3, 6, 12, 24],
        help="Forward look-ahead distances, in SNAPSHOTS (not minutes). "
        "Actual observed snapshot spacing is printed at runtime so you "
        "can translate these into approximate minutes for your data.",
    )
    ap.add_argument(
        "--entry-mode",
        choices=["retracement-reentry", "first-alert", "every-qualified-snapshot"],
        default="retracement-reentry",
        help="retracement-reentry (default): alert ONLY once a symbol has "
        "(a) passed the full existing decision gate, (b) had a confirmed "
        "structural break (resistance/support), and (c) actually retraced "
        "and retested one of {broken S/R, 15m 20-EMA, session VWAP} while "
        "the primary direction stayed intact — using the frozen "
        "_retracement_context()/_break_quality_diagnostic() logic "
        "unmodified. One alert per symbol per day. "
        "first-alert: score only the moment a symbol first enters the "
        "qualified gate (no retracement requirement), like the "
        "dashboard's First Alert. "
        "every-qualified-snapshot: score every qualifying snapshot, no "
        "dedup (inflates sample size).",
    )
    ap.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write backtest_trades.csv and "
        "backtest_summary.csv into.",
    )
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    symbols_filter = (
        {s.strip().upper() for s in args.symbols if s.strip()}
        if args.symbols
        else None
    )

    dates = args.dates or _available_trading_dates(root)
    if not dates:
        print(f"NO TRADING DATES FOUND UNDER {root}")
        return

    print("NTIS SDL DECISION ENGINE BACKTEST")
    print("=" * 100)
    print(f"Root         : {root}")
    print(f"Dates        : {len(dates)} ({dates[0]} .. {dates[-1]})")
    print(f"Symbols      : {'ALL' if not symbols_filter else len(symbols_filter)}")
    print(f"Horizons     : {args.horizons} snapshots ahead")
    print(f"Entry mode   : {args.entry_mode}")
    print("Engine       : existing frozen _process_snapshot() + _rank() "
          "(unchanged)")
    print()

    all_trades: list[pd.DataFrame] = []
    all_gaps: list[float] = []

    for date_str in dates:
        trades, gaps = replay_day(
            root, date_str, args.horizons, symbols_filter, args.entry_mode
        )
        all_gaps.extend(gaps)
        if trades.empty:
            print(f"{date_str}: no qualified alerts")
            continue
        print(f"{date_str}: {len(trades)} scored alerts")
        all_trades.append(trades)

    if not all_trades:
        print()
        print("NO QUALIFIED ALERTS WERE PRODUCED BY THE ENGINE FOR THIS RANGE.")
        return

    trades = pd.concat(all_trades, ignore_index=True)
    summary = summarize(trades, args.horizons)

    trades_path = out_dir / "backtest_trades.csv"
    summary_path = out_dir / "backtest_summary.csv"
    trades.to_csv(trades_path, index=False)
    summary.to_csv(summary_path, index=False)

    if all_gaps:
        median_gap_min = pd.Series(all_gaps).median() / 60.0
        print()
        print(f"Observed median snapshot spacing: {median_gap_min:.1f} minutes "
              f"(use this to interpret --horizons in real time).")

    print()
    print(f"Total scored alerts : {len(trades)}")
    print(f"Trades CSV          : {trades_path}")
    print(f"Summary CSV         : {summary_path}")
    print()
    print("SUMMARY BY DECISION STATE")
    print("-" * 100)
    state_summary = summary[summary["group_by"] == "decision_state"]
    if not state_summary.empty:
        print(state_summary.drop(columns=["group_by"]).to_string(index=False))

    print()
    print("SUMMARY BY EVIDENCE SCORE BUCKET")
    print("-" * 100)
    score_summary = summary[summary["group_by"] == "score_bucket"]
    if not score_summary.empty:
        print(score_summary.drop(columns=["group_by"]).to_string(index=False))

    print()
    print("READ THIS BEFORE ACTING ON RESULTS")
    print("-" * 100)
    print("1. mean_ret_H  = average forward % move, sign-adjusted so positive")
    print("   always means the engine's called direction was correct.")
    print("2. expectancy_H = win_rate-weighted average outcome; this is closer")
    print("   to real edge than win_rate alone, since it accounts for the size")
    print("   of wins vs losses.")
    print("3. Small n_alerts buckets are not statistically reliable — treat")
    print("   anything under ~30 alerts as exploratory, not conclusive.")
    print("4. This is raw price movement only: no costs, slippage, spread, or")
    print("   position-sizing/stop-loss logic is applied.")
    print("5. This is a research tool, not investment advice.")


if __name__ == "__main__":
    main()
