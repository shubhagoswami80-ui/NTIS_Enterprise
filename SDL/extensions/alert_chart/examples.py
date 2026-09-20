from __future__ import annotations

STRONG_CONFIRMATION_RULE = {
    "id": "strong-futures-pece-event",
    "name": "Strong Futures + PE/CE + Breakout/First Alert",
    "enabled": True,
    "priority": 90,
    "rearm": {"mode": "ON_CROSSING", "cooldown_seconds": 0},
    "root": {
        "type": "group", "operator": "ALL", "children": [
            {"type": "condition", "field": "futures.oi_change", "operator": "CROSSED_ABOVE", "value": 10000},
            {"type": "condition", "field": "options.pe_ce_oi_change", "operator": "CROSSED_ABOVE", "value": 10000},
            {"type": "condition", "field": "strength.label", "operator": "=", "value": "STRONG"},
            {"type": "group", "operator": "ANY", "children": [
                {"type": "condition", "field": "direction", "operator": "=", "value": "BULLISH"},
                {"type": "condition", "field": "direction", "operator": "=", "value": "BEARISH"},
            ]},
            {"type": "group", "operator": "ANY", "children": [
                {"type": "condition", "field": "event.breakout", "operator": "=", "value": True},
                {"type": "condition", "field": "event.first_alert", "operator": "=", "value": True},
            ]},
        ],
    },
}


def demo_context(previous_futures: float = 9500, previous_pece: float = 9200):
    return {
        "previous": {
            "futures": {"oi_change": previous_futures},
            "options": {"pe_ce_oi_change": previous_pece},
            "direction": "BULLISH",
            "strength": {"label": "SUPPORTED", "value": 72},
            "event": {"breakout": False, "first_alert": False},
        },
        "current": {
            "symbol": "DEMO",
            "trading_date": "2026-09-20",
            "observation_timestamp": "2026-09-20T10:00:00",
            "futures": {"oi_change": 10500},
            "options": {"pe_ce_oi_change": 11000},
            "direction": "BULLISH",
            "strength": {"label": "STRONG", "value": 84},
            "event": {"breakout": True, "first_alert": False},
        },
    }
