from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    rule_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_events (
    alert_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    trading_date TEXT,
    symbol TEXT NOT NULL,
    observation_timestamp TEXT NOT NULL,
    direction TEXT,
    strength REAL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(rule_id, symbol, observation_timestamp)
);
CREATE INDEX IF NOT EXISTS idx_alert_events_symbol_time ON alert_events(symbol, observation_timestamp);
CREATE INDEX IF NOT EXISTS idx_alert_events_rule_symbol_day ON alert_events(rule_id, symbol, trading_date);
CREATE TABLE IF NOT EXISTS alert_rule_state (
    rule_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    last_matched INTEGER NOT NULL DEFAULT 0,
    armed INTEGER NOT NULL DEFAULT 1,
    last_event_timestamp TEXT,
    last_event_epoch REAL,
    PRIMARY KEY(rule_id, symbol, trading_date)
);
"""


def _epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class AlertStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(SCHEMA)

    def save_rule(self, rule: dict[str, Any], updated_at: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO alert_rules(rule_id,name,enabled,priority,rule_json,updated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(rule_id) DO UPDATE SET name=excluded.name,enabled=excluded.enabled,priority=excluded.priority,rule_json=excluded.rule_json,updated_at=excluded.updated_at",
                (rule["id"], rule["name"], int(rule.get("enabled", True)), int(rule.get("priority", 50)), json.dumps(rule, sort_keys=True), updated_at),
            )

    def list_rules(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT rule_json FROM alert_rules ORDER BY priority DESC, name").fetchall()
        return [json.loads(row[0]) for row in rows]

    def should_emit(self, rule: dict[str, Any], *, symbol: str, trading_date: str, matched: bool, observation_timestamp: str) -> bool:
        """Apply configurable re-arm/cooldown semantics before event persistence."""
        cfg = rule.get("rearm") or {}
        mode = str(cfg.get("mode", "ON_CROSSING")).upper()
        cooldown = max(0, int(cfg.get("cooldown_seconds", 0) or 0))
        obs_epoch = _epoch(observation_timestamp)
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT last_matched, armed, last_event_epoch FROM alert_rule_state WHERE rule_id=? AND symbol=? AND trading_date=?",
                (rule["id"], symbol, trading_date),
            ).fetchone()
            last_matched, armed, last_event_epoch = row if row else (0, 1, None)

            emit = False
            if mode == "MANUAL":
                emit = bool(matched and armed)
            elif mode == "ONCE_PER_SYMBOL_DAY":
                exists = db.execute(
                    "SELECT 1 FROM alert_events WHERE rule_id=? AND symbol=? AND trading_date=? LIMIT 1",
                    (rule["id"], symbol, trading_date),
                ).fetchone() is not None
                emit = bool(matched and not exists)
            elif mode == "COOLDOWN":
                emit = bool(matched)
                if emit and cooldown and obs_epoch is not None and last_event_epoch is not None:
                    emit = (obs_epoch - last_event_epoch) >= cooldown
            else:  # ON_CROSSING
                emit = bool(matched and not last_matched)

            next_armed = armed
            if mode == "MANUAL" and emit:
                next_armed = 0
            elif mode == "ON_CROSSING" and not matched:
                next_armed = 1

            db.execute(
                "INSERT INTO alert_rule_state(rule_id,symbol,trading_date,last_matched,armed,last_event_timestamp,last_event_epoch) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(rule_id,symbol,trading_date) DO UPDATE SET last_matched=excluded.last_matched,armed=excluded.armed",
                (rule["id"], symbol, trading_date, int(bool(matched)), int(next_armed), None, last_event_epoch),
            )
            return emit

    def rearm(self, rule_id: str, symbol: str, trading_date: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE alert_rule_state SET armed=1,last_matched=0 WHERE rule_id=? AND symbol=? AND trading_date=?",
                (rule_id, symbol, trading_date),
            )

    def record_event(self, event: dict[str, Any]) -> bool:
        obs_epoch = _epoch(event.get("observation_timestamp"))
        with sqlite3.connect(self.path) as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO alert_events(alert_id,rule_id,trading_date,symbol,observation_timestamp,direction,strength,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    event["alert_id"], event["rule_id"], event.get("trading_date"), event["symbol"],
                    event["observation_timestamp"], event.get("direction"), event.get("strength"),
                    json.dumps(event, sort_keys=True), event["created_at"],
                ),
            )
            if cur.rowcount == 1:
                db.execute(
                    "UPDATE alert_rule_state SET last_event_timestamp=?,last_event_epoch=? WHERE rule_id=? AND symbol=? AND trading_date=?",
                    (event["observation_timestamp"], obs_epoch, event["rule_id"], event["symbol"], event.get("trading_date") or ""),
                )
            return cur.rowcount == 1

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT payload_json FROM alert_events ORDER BY observation_timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]
