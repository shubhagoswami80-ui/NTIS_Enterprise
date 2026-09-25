from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd


@dataclass(frozen=True)
class RSIResult:
    rsi_15m: float | None
    rsi_30m: float | None
    rsi_1h: float | None
    rsi_2h: float | None
    observation_count: int
    bar_count_15m: int
    current_timestamp: pd.Timestamp | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rsi_15m": self.rsi_15m,
            "rsi_30m": self.rsi_30m,
            "rsi_1h": self.rsi_1h,
            "rsi_2h": self.rsi_2h,
            "rsi_observation_count": self.observation_count,
            "rsi_bar_count_15m": self.bar_count_15m,
            "rsi_current_timestamp": self.current_timestamp,
        }


def wilder_rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Calculate the existing NTIS Wilder RSI formula from chronological closes."""
    if not isinstance(closes, pd.Series) or period <= 0:
        return None
    values = pd.to_numeric(closes, errors="coerce").dropna().astype(float)
    if len(values) < period + 1:
        return None
    delta = values.diff().dropna()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    avg_gain = float(gains.iloc[:period].mean())
    avg_loss = float(losses.iloc[:period].mean())
    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + float(gains.iloc[i])) / period
        avg_loss = ((avg_loss * (period - 1)) + float(losses.iloc[i])) / period
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    return float(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))))


class RSIEngine:
    """Point-in-time MTF RSI evidence; display/evidence only, never a gate."""

    def __init__(self, period: int = 14) -> None:
        self.period = int(period)

    @staticmethod
    def _price(row: Any) -> float | None:
        for key in ("Close", "close", "CMP", "cmp", "current_price", "ltp", "price"):
            try:
                value = pd.to_numeric(row.get(key), errors="coerce")
            except AttributeError:
                value = pd.NA
            if pd.notna(value) and float(value) > 0:
                return float(value)
        return None

    def _observations(
        self,
        history: Iterable[Any] | None,
        current_ts: Any,
    ) -> list[tuple[pd.Timestamp, float]]:
        ts_now = pd.to_datetime(current_ts, errors="coerce")
        if pd.isna(ts_now):
            return []
        ts_now = pd.Timestamp(ts_now)
        today = ts_now.date()
        observations: list[tuple[pd.Timestamp, float]] = []
        for row in history or []:
            ts = pd.to_datetime(
                row.get("source_timestamp", row.get("observation_timestamp", "")),
                errors="coerce",
            )
            price = self._price(row)
            if pd.isna(ts) or price is None:
                continue
            ts = pd.Timestamp(ts)
            if ts > ts_now or ts.date() != today:
                continue
            observations.append((ts, price))
        observations.sort(key=lambda x: x[0])
        return observations

    @staticmethod
    def _session_bucket(ts: pd.Timestamp, minutes: int) -> pd.Timestamp:
        anchor = ts.normalize() + pd.Timedelta(hours=9, minutes=15)
        elapsed = ts - anchor
        steps = int(elapsed.total_seconds() // (minutes * 60))
        return anchor + pd.Timedelta(minutes=steps * minutes)

    def calculate(self, history: Iterable[Any] | None, current_ts: Any) -> RSIResult:
        ts_now = pd.to_datetime(current_ts, errors="coerce")
        if pd.isna(ts_now):
            return RSIResult(None, None, None, None, 0, 0, None)
        ts_now = pd.Timestamp(ts_now)
        observations = self._observations(history, ts_now)
        if not observations:
            return RSIResult(None, None, None, None, 0, 0, ts_now)

        # Preserve the current Git implementation: one latest price per 15m bucket.
        bars: dict[pd.Timestamp, float] = {}
        for ts, price in observations:
            bars[ts.floor("15min")] = float(price)
        ordered = sorted(bars.items(), key=lambda x: x[0])
        rsi_15m = wilder_rsi(
            pd.Series([v for _, v in ordered], dtype="float64"), self.period
        )

        result: dict[str, float | None] = {
            "30m": None,
            "1H": None,
            "2H": None,
        }
        for label, minutes in (("30m", 30), ("1H", 60), ("2H", 120)):
            grouped: dict[pd.Timestamp, float] = {}
            for ts, price in ordered:
                bucket = self._session_bucket(pd.Timestamp(ts), minutes)
                grouped[bucket] = float(price)
            grouped_ordered = sorted(grouped.items(), key=lambda x: x[0])
            if len(grouped_ordered) >= self.period + 1:
                result[label] = wilder_rsi(
                    pd.Series([v for _, v in grouped_ordered], dtype="float64"), self.period
                )

        return RSIResult(
            rsi_15m=rsi_15m,
            rsi_30m=result["30m"],
            rsi_1h=result["1H"],
            rsi_2h=result["2H"],
            observation_count=len(observations),
            bar_count_15m=len(ordered),
            current_timestamp=ts_now,
        )
