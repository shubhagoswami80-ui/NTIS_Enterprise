"""Compact intraday trader alert drawer for NTIS SDL."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Iterable, Mapping

import streamlit as st

from .alert_sound import SoundSettings, sound_html

DEFAULT_RULES = [
    {"name": "Strong Breakout", "field": "Straddle Progress", "operator": ">=", "value": 100.0, "enabled": True, "sound": False},
    {"name": "Breakout", "field": "Straddle Progress", "operator": ">=", "value": 75.0, "enabled": True, "sound": False},
    {"name": "First Alert", "field": "Straddle Progress", "operator": ">=", "value": 25.0, "enabled": True, "sound": False},
    {"name": "Futures OI Spike", "field": "Futures OI Change", "operator": ">", "value": 100000.0, "enabled": True, "sound": False},
    {"name": "PCR Extreme", "field": "PCR", "operator": ">", "value": 3.0, "enabled": True, "sound": False},
    {"name": "High Momentum", "field": "Momentum %", "operator": ">=", "value": 5.0, "enabled": False, "sound": False},
]

FIELDS = [
    "Futures OI Change",
    "Futures OI Change %",
    "PE − CE OI Change",
    "PCR",
    "Momentum %",
    "Straddle Progress",
    "Price Change %",
]
OPERATORS = [">", ">=", "<", "<=", "=", "!="]


@dataclass(frozen=True)
class DrawerConfig:
    max_events: int = 8
    max_history: int = 12


def _text(value: Any, fallback: str = "—") -> str:
    value = "" if value is None else str(value).strip()
    return value or fallback


def _safe_rules(rules: Any) -> list[dict[str, Any]]:
    if not isinstance(rules, list) or not rules:
        return [dict(x) for x in DEFAULT_RULES]
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(rules[:12]):
        if not isinstance(raw, Mapping):
            continue
        field = str(raw.get("field", "PCR"))
        field = field if field in FIELDS else "PCR"
        op = str(raw.get("operator", ">"))
        op = op if op in OPERATORS else ">"
        try:
            value = float(raw.get("value", 0))
        except Exception:
            value = 0.0
        out.append({
            "name": _text(raw.get("name"), f"Rule {i + 1}"),
            "field": field,
            "operator": op,
            "value": value,
            "enabled": bool(raw.get("enabled", True)),
            "sound": bool(raw.get("sound", False)),
        })
    return out or [dict(x) for x in DEFAULT_RULES]


def _event_rows(events: Iterable[Mapping[str, Any]], max_events: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in list(events)[:max(1, int(max_events))]:
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        values = payload.get("values") if isinstance(payload.get("values"), Mapping) else {}
        rule = _text(event.get("rule_name"), "Alert")
        rows.append({
            "symbol": _text(event.get("symbol"), "UNKNOWN").upper(),
            "severity": _text(event.get("severity"), "INFO").upper(),
            "message": _text(event.get("message"), "Alert triggered"),
            "timestamp": _time_only(event.get("observation_timestamp") or event.get("timestamp")),
            "rule": rule,
            "direction": _text(event.get("direction"), ""),
            "strength": _text(event.get("strength"), ""),
            "values": dict(values),
            "trading_date": _text(event.get("trading_date"), ""),
            "alert_id": _text(event.get("alert_id"), ""),
            "sound": bool(event.get("sound", False)),
            "raw": event,
        })
    return rows


def _time_only(value: Any) -> str:
    text = _text(value, "—")
    if "T" in text:
        text = text.split("T", 1)[1]
    if "+" in text:
        text = text.split("+", 1)[0]
    return text[:8]


def _fmt_value(field: str, value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        n = float(value)
    except Exception:
        return _text(value)
    if field in {"PCR"}:
        return f"{n:.2f}"
    if field in {"Momentum %", "Straddle Progress", "Price Change %", "Futures OI Change %"}:
        return f"{n:.1f}%"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:g}"


def _trigger_text(row: Mapping[str, Any]) -> tuple[str, str]:
    message = _text(row.get("message"), "Alert triggered")
    values = row.get("values") if isinstance(row.get("values"), Mapping) else {}
    rule = _text(row.get("rule"), "Alert")
    field = None
    for candidate in FIELDS:
        if candidate in message:
            field = candidate
            break
    if field is None:
        return rule, message
    current = _fmt_value(field, values.get(field))
    return rule, f"{field}  {current}  ·  {message}"


def _severity_class(severity: str) -> str:
    s = str(severity).upper()
    if s in {"HIGH", "CRITICAL"}:
        return "high"
    if "BREAK" in s or s == "ALERT":
        return "breakout"
    return "info"


def _rule_short_name(rule: Mapping[str, Any]) -> str:
    name = _text(rule.get("name"), "Rule")
    if name == "First Alert":
        return "EARLY"
    if name == "Strong Breakout":
        return "STRONG"
    if name == "Futures OI Spike":
        return "FUT OI"
    if name == "PCR Extreme":
        return "PCR"
    if name == "High Momentum":
        return "MOM"
    return name.upper()[:10]


def render_alert_drawer(
    events: Iterable[Mapping[str, Any]] = (),
    *,
    config: DrawerConfig | None = None,
    history_events: Iterable[Mapping[str, Any]] | None = None,
    sound_enabled: bool = False,
    sound_volume: float = 0.35,
    sound_tone: str = "soft",
    new_alert: bool = False,
    new_alert_sound: bool = False,
    rules: list[dict[str, Any]] | None = None,
    chart_provider=None,
    diagnostic: str | None = None,
) -> dict[str, Any]:
    cfg = config or DrawerConfig()
    rows = _event_rows(events, cfg.max_events)
    history_rows = _event_rows(history_events or (), cfg.max_history)
    current_rules = _safe_rules(rules)

    enabled_count = sum(bool(r.get("enabled", True)) for r in current_rules)
    sound_count = sum(bool(r.get("sound", False)) and bool(r.get("enabled", True)) for r in current_rules)
    label = f"🔔 {len(rows)}" if rows else "🔔"

    st.markdown(
        """
<style>
/* B4 trader drawer: compact, right-anchored, information-first. */
[data-testid="stPopover"] button{position:fixed!important;right:16px!important;top:112px!important;z-index:1000000!important;min-width:40px!important;width:40px!important;height:34px!important;padding:0!important;border-radius:8px!important;background:#0d1b2e!important;border:1px solid #3a5a82!important;color:#fff!important;font-size:15px!important;line-height:1!important;box-shadow:0 4px 14px rgba(0,0,0,.18)!important}
[data-testid="stPopover"] button svg{display:none!important}
[data-testid="stPopover"] button span{font-size:0!important}
[data-testid="stPopover"] button span::before{content:'🔔';font-size:15px!important}
[data-testid="stPopoverBody"]{position:fixed!important;right:12px!important;top:74px!important;left:auto!important;transform:none!important;width:390px!important;max-width:calc(100vw - 24px)!important;max-height:calc(100vh - 88px)!important;overflow-y:auto!important;overflow-x:hidden!important;padding:9px!important;background:#071321!important;border:1px solid #29476e!important;border-radius:10px!important;box-shadow:0 20px 55px rgba(0,0,0,.55)!important;z-index:999999!important}
[data-testid="stPopoverBody"] > div{max-width:none!important}
[data-testid="stPopoverBody"] .stButton button{min-height:27px!important;padding:2px 7px!important;font-size:10px!important}
[data-testid="stPopoverBody"] label{font-size:9px!important}
[data-testid="stPopoverBody"] [data-testid="stTabs"] button{font-size:10px!important;padding:4px 7px!important}
[data-testid="stPopoverBody"] [data-testid="stExpander"]{margin:4px 0!important;border:1px solid #29476e!important;background:#091729!important}
[data-testid="stPopoverBody"] [data-testid="stExpanderDetails"]{padding:6px 8px!important}
.b4-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
.b4-title{font-size:14px;font-weight:700;color:#f3f7fb}
.b4-sub{font-size:8px;color:#8fa5c0}
.b4-summary{display:flex;gap:4px;flex-wrap:wrap;margin:2px 0 7px}
.b4-chip{font-size:8px;color:#a9bdd4;background:#0b1c31;border:1px solid #203b5d;border-radius:5px;padding:2px 5px}
.b4-chip.hot{color:#fff1d0;border-color:#805f24;background:#2b210e}
.b4-card{padding:6px 6px 7px;margin:3px 0;border:1px solid #203b5d;border-radius:7px;background:#091827}
.b4-card.high{border-left:3px solid #ef9b3a}.b4-card.breakout{border-left:3px solid #53d28a}.b4-card.info{border-left:3px solid #55718f}
.b4-line1{display:flex;align-items:center;gap:5px}
.b4-symbol{font-size:12px;font-weight:800;color:#fff}.b4-time{margin-left:auto;font-size:8px;color:#8095ae}
.b4-badge{font-size:7px;font-weight:800;letter-spacing:.4px;border-radius:4px;padding:2px 4px;background:#18314d;color:#a9c7e5}
.b4-trigger{font-size:9px;color:#d4dfec;margin-top:3px;line-height:1.35}
.b4-dir{font-size:8px;color:#89a3bf;margin-top:2px}
.b4-empty{font-size:9px;color:#8196ad;padding:10px 3px;text-align:center}
.b4-rule-row{padding:5px 0;border-bottom:1px solid #1b304c}
.b4-rule-name{font-size:9px;color:#d7e2ee;font-weight:700}
.b4-rule-cond{font-size:8px;color:#8298b1;margin-top:2px}
.b4-help{font-size:8px;color:#7e94ad;line-height:1.35;margin:3px 0 6px}
.b4-section-label{font-size:8px;font-weight:800;letter-spacing:.8px;color:#7189a5;margin:6px 0 2px}
.b4-rule-mini{display:flex;flex-direction:column;line-height:1.15;padding-top:2px}
.b4-rule-mini b{font-size:9px;color:#e4edf7}
.b4-rule-mini span{font-size:7px;color:#7f96ae;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[data-testid="stPopoverBody"] [data-testid="stCheckbox"] label{font-size:8px!important}
[data-testid="stPopoverBody"] [data-testid="stSlider"]{padding-top:0!important;padding-bottom:0!important}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.popover(label, use_container_width=False):
        st.markdown(
            f"<div class='b4-top'><div><span class='b4-title'>Intraday Alerts</span><div class='b4-sub'>crossing alerts · source time · no score/filter change</div></div><span class='b4-badge'>{enabled_count} ON</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='b4-summary'><span class='b4-chip{' hot' if new_alert else ''}'>NEW {'YES' if new_alert else '—'}</span><span class='b4-chip'>RECENT {len(rows)}</span><span class='b4-chip'>HISTORY {len(history_rows)}</span><span class='b4-chip'>SOUND {'ON' if sound_enabled else 'OFF'}</span>{f"<span class='b4-chip'>RULE SOUND {sound_count}</span>" if sound_count else ''}</div>",
            unsafe_allow_html=True,
        )

        live_tab, history_tab, setup_tab = st.tabs(["LIVE", "HISTORY", "SETUP"])

        with live_tab:
            if rows:
                for row in rows:
                    rule_name, trigger = _trigger_text(row)
                    direction = _text(row.get("direction"), "")
                    strength = _text(row.get("strength"), "")
                    detail = " · ".join(x for x in (direction, strength) if x)
                    st.markdown(
                        f"<div class='b4-card {_severity_class(row['severity'])}'><div class='b4-line1'><span class='b4-symbol'>{escape(row['symbol'])}</span><span class='b4-badge'>{escape(_rule_short_name({'name': rule_name}))}</span><span class='b4-time'>{escape(row['timestamp'])}</span></div><div class='b4-trigger'>{escape(trigger)}</div>{f"<div class='b4-dir'>{escape(detail)}</div>" if detail else ''}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("<div class='b4-empty'>No new threshold crossing.<br>Decision Board / Queue continue independently.</div>", unsafe_allow_html=True)

        with history_tab:
            if history_rows:
                for row in history_rows:
                    rule_name, trigger = _trigger_text(row)
                    st.markdown(
                        f"<div class='b4-card info'><div class='b4-line1'><span class='b4-symbol'>{escape(row['symbol'])}</span><span class='b4-badge'>{escape(_rule_short_name({'name': rule_name}))}</span><span class='b4-time'>{escape(row['timestamp'])}</span></div><div class='b4-trigger'>{escape(trigger)}</div></div>",
                        unsafe_allow_html=True,
                    )
                if chart_provider is not None:
                    chart_symbols = list(dict.fromkeys(row["symbol"] for row in history_rows))
                    selected_symbol = st.selectbox("Chart", chart_symbols, key="sdl_alert_chart_symbol")
                    selected_event = next((e for e in (history_events or ()) if _text(e.get("symbol"), "UNKNOWN").upper() == selected_symbol), None)
                    if selected_event is not None:
                        try:
                            chart_df = chart_provider(selected_event)
                            if chart_df is not None and not chart_df.empty:
                                if "Observation" in chart_df.columns and "Close" in chart_df.columns:
                                    st.line_chart(chart_df.set_index("Observation")["Close"])
                                else:
                                    st.dataframe(chart_df, use_container_width=True, hide_index=True)
                        except Exception as exc:
                            st.caption(f"Chart unavailable: {type(exc).__name__}: {exc}")
            else:
                st.markdown("<div class='b4-empty'>No persisted alert history.</div>", unsafe_allow_html=True)

        with setup_tab:
            st.markdown("<div class='b4-help'>Compact controls only. Alert rules are independent of SDL scoring, Radar, Queue and Replay.</div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([0.9, 1.15, 1.35])
            with c1:
                enabled = st.toggle("Sound", value=bool(sound_enabled), key="sdl_alert_sound_enabled")
            with c2:
                tone_options = ["long", "double", "single", "soft"]
                tone_value = sound_tone if sound_tone in tone_options else "long"
                tone = st.selectbox("Tone", tone_options, index=tone_options.index(tone_value), key="sdl_alert_sound_tone")
            with c3:
                volume = st.slider("Vol", 0.05, 1.0, max(0.05, min(float(sound_volume), 1.0)), 0.05, key="sdl_alert_sound_volume")
            st.components.v1.html(sound_html(SoundSettings(True, float(volume), tone), test_button=True, nonce="sdl-b41-test"), height=38)

            st.markdown("<div class='b4-section-label'>RULES</div>", unsafe_allow_html=True)
            for idx, rule in enumerate(current_rules):
                r1, r2, r3 = st.columns([0.42, 1.45, 1.0])
                with r1:
                    rule_enabled = st.checkbox("", value=bool(rule["enabled"]), key=f"sdl_rule_enabled_{idx}", label_visibility="collapsed")
                with r2:
                    st.markdown(f"<div class='b4-rule-mini'><b>{escape(_rule_short_name(rule))}</b><span>{escape(str(rule['field']))} {escape(str(rule['operator']))} {float(rule['value']):g}</span></div>", unsafe_allow_html=True)
                with r3:
                    rule_sound = st.checkbox("Sound", value=bool(rule["sound"]), key=f"sdl_rule_sound_{idx}")
                current_rules[idx]["enabled"] = bool(rule_enabled)
                current_rules[idx]["sound"] = bool(rule_sound)

            with st.expander("Edit thresholds", expanded=False):
                for idx, rule in enumerate(current_rules):
                    f, o, v = st.columns([1.65, 0.65, 0.8])
                    with f:
                        field = st.selectbox("Field", FIELDS, index=FIELDS.index(rule["field"]), key=f"sdl_rule_field_{idx}")
                    with o:
                        op = st.selectbox("Op", OPERATORS, index=OPERATORS.index(rule["operator"]), key=f"sdl_rule_op_{idx}")
                    with v:
                        value = st.number_input("Value", value=float(rule["value"]), step=1.0, key=f"sdl_rule_value_{idx}")
                    current_rules[idx]["field"] = field
                    current_rules[idx]["operator"] = op
                    current_rules[idx]["value"] = float(value)

                if st.button("↺ Reset defaults", key="sdl_reset_alert_rules"):
                    for idx, rule in enumerate(DEFAULT_RULES):
                        st.session_state[f"sdl_rule_enabled_{idx}"] = bool(rule["enabled"])
                        st.session_state[f"sdl_rule_sound_{idx}"] = bool(rule["sound"])
                        st.session_state[f"sdl_rule_field_{idx}"] = rule["field"]
                        st.session_state[f"sdl_rule_op_{idx}"] = rule["operator"]
                        st.session_state[f"sdl_rule_value_{idx}"] = float(rule["value"])
                    st.rerun()

        should_sound = bool(new_alert and new_alert_sound and enabled)

    # Audio remains outside the popover so a closed drawer can still announce a new event.
    should_sound = bool(new_alert and new_alert_sound and enabled)
    st.components.v1.html(
        sound_html(SoundSettings(enabled=enabled, volume=volume, tone=tone), trigger=should_sound, nonce="sdl-b41-alert"),
        height=1,
    )
    return {
        "enabled": bool(enabled),
        "volume": float(volume),
        "tone": str(tone),
        "rules": current_rules,
    }
