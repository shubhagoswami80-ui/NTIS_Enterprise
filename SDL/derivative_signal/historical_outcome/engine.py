from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence
import pandas as pd


@dataclass(frozen=True)
class OutcomeConfig:
    intraday_horizons_minutes: tuple[int, ...] = (5, 15, 30, 60)
    include_session_close: bool = True
    include_next_session: bool = True


class HistoricalOutcomeEngine:
    """Point-in-time outcome evaluator for already-emitted evidence events.

    Event/evidence columns are never used to construct the future observations.
    Only observations strictly after event_timestamp are eligible.

    Expected event columns:
      symbol, event_timestamp
    Optional:
      direction (BULLISH/BEARISH), event_price

    Expected observation columns:
      symbol, observation_timestamp, close
    Optional:
      session_date

    This layer is evidence-only. It does not select symbols or alter SDL state.
    """

    def __init__(self, config: OutcomeConfig | None = None):
        self.config = config or OutcomeConfig()

    @staticmethod
    def _clean_symbol(value) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _numeric(value):
        try:
            if pd.isna(value) or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _prepare_events(events: pd.DataFrame) -> pd.DataFrame:
        out = events.copy()
        if "symbol" not in out.columns and "Symbol" in out.columns:
            out["symbol"] = out["Symbol"]
        if "event_timestamp" not in out.columns:
            raise KeyError("events requires event_timestamp")
        if "symbol" not in out.columns:
            raise KeyError("events requires symbol")
        out["symbol"] = out["symbol"].map(HistoricalOutcomeEngine._clean_symbol)
        out["event_timestamp"] = pd.to_datetime(
            out["event_timestamp"], errors="coerce"
        )
        out = out[out["symbol"].ne("") & out["event_timestamp"].notna()].copy()
        return out.reset_index(drop=True)

    @staticmethod
    def _prepare_observations(observations: pd.DataFrame) -> pd.DataFrame:
        out = observations.copy()
        if "symbol" not in out.columns and "Symbol" in out.columns:
            out["symbol"] = out["Symbol"]
        if "observation_timestamp" not in out.columns:
            raise KeyError("observations requires observation_timestamp")
        if "close" not in out.columns:
            for candidate in ("Close", "CMP", "Price", "Current Price"):
                if candidate in out.columns:
                    out["close"] = out[candidate]
                    break
        if "close" not in out.columns:
            raise KeyError("observations requires close")
        if "symbol" not in out.columns:
            raise KeyError("observations requires symbol")
        out["symbol"] = out["symbol"].map(HistoricalOutcomeEngine._clean_symbol)
        out["observation_timestamp"] = pd.to_datetime(
            out["observation_timestamp"], errors="coerce"
        )
        out["close"] = pd.to_numeric(out["close"], errors="coerce")
        out = out[
            out["symbol"].ne("")
            & out["observation_timestamp"].notna()
            & out["close"].notna()
        ].copy()
        if "session_date" not in out.columns:
            out["session_date"] = out["observation_timestamp"].dt.date.astype(str)
        else:
            out["session_date"] = out["session_date"].astype(str)
        return out.sort_values(
            ["symbol", "observation_timestamp"], kind="mergesort"
        ).reset_index(drop=True)

    @staticmethod
    def _direction_outcome(direction, return_pct):
        if return_pct is None:
            return "UNRESOLVED"
        d = str(direction or "").strip().upper()
        if d in {"BULLISH", "BUY", "LONG", "STRONG BUY"}:
            return "POSITIVE" if return_pct > 0 else "NEGATIVE" if return_pct < 0 else "FLAT"
        if d in {"BEARISH", "SELL", "SHORT", "STRONG SELL"}:
            return "POSITIVE" if return_pct < 0 else "NEGATIVE" if return_pct > 0 else "FLAT"
        return "UNSPECIFIED_DIRECTION"

    def evaluate(self, events: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
        ev = self._prepare_events(events)
        obs = self._prepare_observations(observations)
        rows = []

        grouped = {symbol: frame for symbol, frame in obs.groupby("symbol", sort=False)}

        for event_id, event in ev.iterrows():
            symbol = event["symbol"]
            event_ts = event["event_timestamp"]
            group = grouped.get(symbol, pd.DataFrame())
            if group.empty:
                continue

            # Event price is authoritative if present; otherwise use the first
            # strictly-later observation only as a documented fallback baseline.
            event_price = self._numeric(event.get("event_price"))
            if event_price is None:
                prior_or_same = group[group["observation_timestamp"] <= event_ts]
                if not prior_or_same.empty:
                    event_price = float(prior_or_same.iloc[-1]["close"])

            future = group[group["observation_timestamp"] > event_ts].copy()
            if future.empty:
                continue

            direction = event.get("direction", event.get("Direction", ""))

            base = {
                "event_id": int(event_id),
                "symbol": symbol,
                "event_timestamp": event_ts,
                "event_price": event_price,
                "direction": direction,
            }
            if "event" in event.index:
                base["event"] = event["event"]
            if "horizon" in event.index:
                base["historical_horizon"] = event["horizon"]

            for minutes in self.config.intraday_horizons_minutes:
                target_ts = event_ts + pd.Timedelta(minutes=int(minutes))
                candidates = future[future["observation_timestamp"] >= target_ts]
                if candidates.empty:
                    continue
                point = candidates.iloc[0]
                close = float(point["close"])
                ret = (
                    ((close - event_price) / event_price) * 100
                    if event_price not in (None, 0)
                    else None
                )
                record = dict(base)
                record.update({
                    "outcome_window": f"{minutes}m",
                    "target_timestamp": target_ts,
                    "observation_timestamp": point["observation_timestamp"],
                    "outcome_price": close,
                    "return_pct": ret,
                    "directional_outcome": self._direction_outcome(direction, ret),
                    "is_forward_only": True,
                    "outcome_type": "INTRADAY",
                })
                rows.append(record)

            if self.config.include_session_close:
                event_session = str(event_ts.date())
                same_session = future[future["session_date"].eq(event_session)]
                if not same_session.empty:
                    point = same_session.iloc[-1]
                    close = float(point["close"])
                    ret = (
                        ((close - event_price) / event_price) * 100
                        if event_price not in (None, 0)
                        else None
                    )
                    record = dict(base)
                    record.update({
                        "outcome_window": "SESSION_CLOSE",
                        "target_timestamp": point["observation_timestamp"],
                        "observation_timestamp": point["observation_timestamp"],
                        "outcome_price": close,
                        "return_pct": ret,
                        "directional_outcome": self._direction_outcome(direction, ret),
                        "is_forward_only": True,
                        "outcome_type": "SESSION_CLOSE",
                    })
                    rows.append(record)

            if self.config.include_next_session:
                later_sessions = sorted(
                    s for s in future["session_date"].unique()
                    if s > str(event_ts.date())
                )
                if later_sessions:
                    next_session = later_sessions[0]
                    next_rows = future[future["session_date"].eq(next_session)]
                    if not next_rows.empty:
                        point = next_rows.iloc[0]
                        close = float(point["close"])
                        ret = (
                            ((close - event_price) / event_price) * 100
                            if event_price not in (None, 0)
                            else None
                        )
                        record = dict(base)
                        record.update({
                            "outcome_window": "NEXT_SESSION_OPEN",
                            "target_timestamp": point["observation_timestamp"],
                            "observation_timestamp": point["observation_timestamp"],
                            "outcome_price": close,
                            "return_pct": ret,
                            "directional_outcome": self._direction_outcome(direction, ret),
                            "is_forward_only": True,
                            "outcome_type": "BTST_NEXT_SESSION",
                        })
                        rows.append(record)

        return pd.DataFrame(rows)


def evaluate_historical_outcomes(
    events: pd.DataFrame,
    observations: pd.DataFrame,
    config: OutcomeConfig | None = None,
) -> pd.DataFrame:
    return HistoricalOutcomeEngine(config).evaluate(events, observations)
