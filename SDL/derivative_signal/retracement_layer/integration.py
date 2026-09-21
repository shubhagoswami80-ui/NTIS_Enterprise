from __future__ import annotations

from typing import Any, Iterable

from .adapter import process_qualified_pool
from .engine import RetracementEngine


STATE_KEY = "retracement_engine_state"


class RetracementIntegration:
    """Durable, fault-isolated bridge for the post-qualification layer.

    The caller remains responsible for the authoritative SDL qualification
    boundary (normally _rank(result)). This class only receives that already
    qualified pool and maintains retracement state across observations.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.engine = RetracementEngine()
        self.restore(state or {})

    def restore(self, state: dict[str, Any] | None) -> None:
        payload = state.get(STATE_KEY, {}) if isinstance(state, dict) else {}
        self.engine.restore(payload if isinstance(payload, dict) else {})

    def snapshot(self) -> dict[str, Any]:
        return {STATE_KEY: self.engine.snapshot()}

    def process_qualified_rows(
        self,
        rows: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Process only the rows explicitly supplied by the SDL qualification boundary."""
        return process_qualified_pool(self.engine, list(rows))

    def process_qualified_frame(self, frame: Any) -> list[dict[str, Any]]:
        """Pandas-optional convenience wrapper; avoids making pandas a layer dependency."""
        if frame is None or not hasattr(frame, "to_dict"):
            return []
        try:
            rows = frame.to_dict(orient="records")
        except Exception:
            return []
        return self.process_qualified_rows(rows)
