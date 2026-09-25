from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import math
import re

import pandas as pd


DEFAULT_HORIZONS = (2, 3, 4, 5, 10, 15, 20, 25, 30)


@dataclass(frozen=True)
class DifferentialConfig:
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    ratio_threshold: float = 2.0
    z_threshold: float = 2.0
    time_tolerance_minutes: int = 7


@dataclass
class DifferentialResult:
    rows: pd.DataFrame
    missing_metrics: list[str] = field(default_factory=list)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    lookup = {_norm(c): c for c in df.columns}
    for alias in aliases:
        if _norm(alias) in lookup:
            return lookup[_norm(alias)]
    return None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(pd.Series(values, dtype="float64").median())


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(pd.Series(values, dtype="float64").mean())


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(pd.Series(values, dtype="float64").quantile(q))


def _robust_z(current: float, values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    s = pd.Series(values, dtype="float64")
    med = float(s.median())
    mad = float((s - med).abs().median())
    if mad == 0:
        return None
    return float(0.6745 * (current - med) / mad)


def _ratio(current: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return float(current / baseline)


def _prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    d = df.copy()

    date_col = _find_column(d, ("trading_date", "date", "trade_date"))
    ts_col = _find_column(d, ("observation_timestamp", "timestamp", "observed_at", "observation_time"))
    sym_col = _find_column(d, ("symbol", "ticker", "Symbol", "Ticker"))

    if not date_col or not ts_col or not sym_col:
        missing = [x for x, c in (("trading_date", date_col), ("observation_timestamp", ts_col), ("symbol", sym_col)) if not c]
        raise ValueError("Missing required columns: " + ", ".join(missing))

    d["_trading_date"] = pd.to_datetime(d[date_col], errors="coerce").dt.date
    d["_timestamp"] = pd.to_datetime(d[ts_col], errors="coerce")
    d["_symbol"] = d[sym_col].astype(str).str.strip().str.upper()
    d = d.dropna(subset=["_trading_date", "_timestamp"])
    d = d[d["_symbol"].ne("") & d["_symbol"].ne("NAN")]
    d = d.sort_values(["_trading_date", "_timestamp", "_symbol"]).drop_duplicates(
        ["_trading_date", "_timestamp", "_symbol"], keep="last"
    )

    aliases = {
        "volume": ("volume", "tot volume", "total volume", "volume_chg_pct"),
        "fut_oi": ("fut oi", "future oi", "futures oi"),
        "fut_oi_chg_pct": ("fut oi chg %", "future oi chg %", "futures oi chg %"),
        "fut_buildup": ("fut buildup", "future buildup", "futures buildup"),
        "ce_oi_chg_pct": (
            "ce oi chg %",
            "call oi chg %",
            "call oi change %",
            "ce oi change %",
        ),
        "pe_oi_chg_pct": (
            "pe oi chg %",
            "put oi chg %",
            "put oi change %",
            "pe oi change %",
        ),
        "ce_oi": ("ce oi", "call oi", "call open interest"),
        "pe_oi": ("pe oi", "put oi", "put open interest"),
    }
    resolved = {}
    for key, names in aliases.items():
        c = _find_column(d, names)
        if c:
            d[f"_metric_{key}"] = _numeric(d[c])
            resolved[key] = c

    return d, resolved


def _metric_value(row: pd.Series, metric: str) -> float | None:
    v = row.get(f"_metric_{metric}")
    if v is None or pd.isna(v):
        return None
    return float(v)


def _futures_event_value(row: pd.Series, event: str) -> float | None:
    text = str(row.get("fut_buildup", "")).strip().upper()
    mapping = {
        "FUTURES_LONG_BUILDUP": {"LB", "LONG", "LONG BUILDUP"},
        "FUTURES_SHORT_BUILDUP": {"SB", "SHORT", "SHORT BUILDUP"},
        "FUTURES_SHORT_COVERING": {"SC", "SHORT COVERING"},
        "FUTURES_LONG_UNWINDING": {"LU", "LONG UNWINDING", "LONG UNWIND"},
    }
    if text not in mapping.get(event, set()):
        return None
    return _metric_value(row, "fut_oi_chg_pct") or _metric_value(row, "fut_oi")


def _same_pit_candidates(
    d: pd.DataFrame,
    current_date,
    current_ts: pd.Timestamp,
    horizon: int,
    tolerance_minutes: int,
) -> tuple[pd.DataFrame, int]:
    prior_dates = sorted(
        {x for x in d["_trading_date"].unique() if x < current_date},
        reverse=True,
    )
    selected = prior_dates[horizon - 1 : horizon] if len(prior_dates) >= horizon else []
    if not selected:
        return d.iloc[0:0], 0

    target_time = current_ts.time()
    rows = []
    for day in selected:
        day_rows = d[d["_trading_date"].eq(day)]
        if day_rows.empty:
            continue
        deltas = (
            day_rows["_timestamp"].dt.hour * 3600
            + day_rows["_timestamp"].dt.minute * 60
            + day_rows["_timestamp"].dt.second
            - (target_time.hour * 3600 + target_time.minute * 60 + target_time.second)
        ).abs()
        idx = deltas.idxmin()
        if float(deltas.loc[idx]) <= tolerance_minutes * 60:
            rows.append(day_rows.loc[[idx]])
    if not rows:
        return d.iloc[0:0], 0
    return pd.concat(rows, ignore_index=False), len(rows)


class PITDifferentialEngine:
    """Point-in-time differential evidence; never a stock-selection gate."""

    def __init__(self, config: DifferentialConfig | None = None):
        self.config = config or DifferentialConfig()

    def analyze(self, frame: pd.DataFrame, current_timestamp: Any | None = None) -> DifferentialResult:
        d, resolved = _prepare(frame)
        if d.empty:
            return DifferentialResult(pd.DataFrame(), [])

        if current_timestamp is None:
            current_timestamp = d["_timestamp"].max()
        current_ts = pd.Timestamp(current_timestamp)
        current_date = current_ts.date()

        current_rows = d[d["_timestamp"].eq(current_ts) & d["_trading_date"].eq(current_date)]
        if current_rows.empty:
            same_day = d[d["_trading_date"].eq(current_date)]
            if same_day.empty:
                return DifferentialResult(pd.DataFrame(), [])
            delta = (same_day["_timestamp"] - current_ts).abs()
            current_rows = same_day.loc[[delta.idxmin()]]

        detector_defs = [
            ("VOLUME_SURGE", "volume", "magnitude"),
            ("FUTURES_LONG_BUILDUP", "futures_event", "magnitude"),
            ("FUTURES_SHORT_COVERING", "futures_event", "magnitude"),
            ("FUTURES_SHORT_BUILDUP", "futures_event", "magnitude"),
            ("FUTURES_LONG_UNWINDING", "futures_event", "magnitude"),
            ("CE_OI_BUILDUP", "ce_oi_chg_pct", "magnitude"),
            ("PE_OI_BUILDUP", "pe_oi_chg_pct", "magnitude"),
        ]

        output = []
        for _, cur in current_rows.iterrows():
            symbol = cur["_symbol"]
            for event, metric, mode in detector_defs:
                if metric == "futures_event":
                    current_value = _futures_event_value(cur, event)
                else:
                    current_value = _metric_value(cur, metric)
                if current_value is None:
                    continue

                for horizon in self.config.horizons:
                    hist_rows, count = _same_pit_candidates(
                        d, current_date, current_ts, horizon, self.config.time_tolerance_minutes
                    )
                    hist_rows = hist_rows[hist_rows["_symbol"].eq(symbol)]
                    hist_values = []
                    for _, hr in hist_rows.iterrows():
                        if metric == "futures_event":
                            v = _futures_event_value(hr, event)
                        else:
                            v = _metric_value(hr, metric)
                        if v is not None and math.isfinite(v):
                            hist_values.append(abs(v))

                    current_mag = abs(float(current_value))
                    med = _median(hist_values)
                    mean = _mean(hist_values)
                    p90 = _percentile(hist_values, 0.90)
                    ratio = _ratio(current_mag, med)
                    z = _robust_z(current_mag, hist_values)
                    unusual = bool(
                        ratio is not None and ratio >= self.config.ratio_threshold
                    ) or bool(z is not None and z >= self.config.z_threshold)

                    output.append({
                        "symbol": symbol,
                        "event": event,
                        "current_timestamp": current_ts,
                        "current_value": float(current_value),
                        "current_magnitude": current_mag,
                        "historical_median": med,
                        "historical_mean": mean,
                        "historical_p90": p90,
                        "current_vs_median_ratio": ratio,
                        "robust_z": z,
                        "historical_sessions": count,
                        "horizon_days": horizon,
                        "unusual": unusual,
                    })

        result = pd.DataFrame(output)
        missing = []
        for metric in ("volume", "fut_oi_chg_pct", "fut_buildup", "ce_oi_chg_pct", "pe_oi_chg_pct"):
            if metric not in resolved:
                missing.append(metric)
        return DifferentialResult(result, missing)


def build_pit_differential(
    frame: pd.DataFrame,
    current_timestamp: Any | None = None,
    config: DifferentialConfig | None = None,
) -> pd.DataFrame:
    return PITDifferentialEngine(config).analyze(frame, current_timestamp).rows
