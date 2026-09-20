"""NTIS SDL B4 compact alert drawer.

Presentation/configuration sidecar only. SDL scoring, replay, Futures mapping,
and cache logic remain outside this module.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping
import html

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
    "Futures OI Change", "Futures OI Change %", "PE − CE OI Change",
    "PCR", "Momentum %", "Straddle Progress", "Price Change %",
]
OPERATORS = [">", ">=", "<", "<=", "=", "!="]


def _safe_rules(rules: Any) -> list[dict[str, Any]]:
    if not isinstance(rules, list) or not rules:
        return [dict(x) for x in DEFAULT_RULES]
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(rules[:12]):
        if not isinstance(raw, Mapping):
            continue
        field = str(raw.get("field", "PCR"))
        if field not in FIELDS:
            field = "PCR"
        op = str(raw.get("operator", ">"))
        if op not in OPERATORS:
            op = ">"
        try:
            value = float(raw.get("value", 0))
        except Exception:
            value = 0.0
        out.append({
            "name": str(raw.get("name") or f"Rule {i + 1}"),
            "field": field,
            "operator": op,
            "value": value,
            "enabled": bool(raw.get("enabled", True)),
            "sound": bool(raw.get("sound", False)),
        })
    return out or [dict(x) for x in DEFAULT_RULES]


def _event_rows(events: Iterable[Mapping[str, Any]], max_events: int) -> list[dict[str, str]]:
    rows = []
    for event in list(events)[:max(1, int(max_events))]:
        reasons = event.get("matched_conditions") or []
        message = event.get("message") or (" · ".join(map(str, reasons)) if reasons else "Alert triggered")
        rows.append({
            "symbol": str(event.get("symbol") or "UNKNOWN"),
            "severity": str(event.get("severity") or "INFO").upper(),
            "message": str(message),
            "timestamp": str(event.get("observation_timestamp") or event.get("timestamp") or "—"),
            "rule": str(event.get("rule_name") or "Alert rule"),
        })
    return rows


def render_alert_drawer(
    events: Iterable[Mapping[str, Any]] = (),
    *,
    max_events: int = 8,
    sound_enabled: bool = False,
    sound_volume: float = 0.35,
    sound_tone: str = "soft",
    new_alert: bool = False,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = _event_rows(events, max_events)
    current_rules = _safe_rules(rules)
    enabled = bool(sound_enabled)
    volume = max(0.05, min(float(sound_volume), 1.0))
    tone = sound_tone if sound_tone in {"soft", "single", "double"} else "soft"

    st.markdown("""
    <style>
      /* B4 trigger: keep only the bell; suppress Streamlit's popover label/icon text. */
      [data-testid="stPopover"] > button {
        min-width:42px!important;width:42px!important;height:36px!important;
        padding:0!important;border-radius:8px!important;background:#0d1b2e!important;
        border:1px solid #315277!important;color:#fff!important;font-size:0!important;
      }
      [data-testid="stPopover"] > button * { font-size:0!important; }
      [data-testid="stPopover"] > button::after {
        content:'🔔';font-size:17px!important;line-height:1!important;
      }
      [data-testid="stPopoverBody"] {
        position:fixed!important;right:12px!important;left:auto!important;top:74px!important;
        transform:none!important;width:500px!important;max-width:calc(100vw - 24px)!important;
        max-height:calc(100vh - 88px)!important;overflow-y:auto!important;overflow-x:hidden!important;
        padding:10px!important;background:#071321!important;border:1px solid #29476e!important;
        border-radius:10px!important;box-shadow:0 20px 55px rgba(0,0,0,.58)!important;z-index:999999!important;
      }
      [data-testid="stPopoverBody"] > div { max-width:none!important; }
      [data-testid="stPopoverBody"] .stButton button { min-height:29px!important;padding:3px 8px!important;font-size:10px!important; }
      [data-testid="stPopoverBody"] label { font-size:9px!important; }
      [data-testid="stPopoverBody"] input { font-size:11px!important; }
      [data-testid="stPopoverBody"] [data-testid="stSelectbox"] { margin:0!important; }
      [data-testid="stPopoverBody"] [data-testid="stNumberInput"] { margin:0!important; }
      .b4-rule { border-top:1px solid #1c3551;padding:7px 0 6px; }
      .b4-rule-top { display:flex;align-items:center;justify-content:space-between;gap:8px; }
      .b4-rule-name { color:#eef4fb;font-size:11px;font-weight:900; }
      .b4-rule-summary { color:#8fa5c0;font-size:9px;margin-top:3px; }
      .b4-section { color:#8fa5c0;font-size:9px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;margin:8px 0 4px; }
      .b4-event { padding:6px 0;border-bottom:1px solid #1d334d; }
      .b4-event-main { color:#edf4fc;font-size:10px;font-weight:800; }
      .b4-event-meta { color:#8fa5c0;font-size:9px;margin-top:2px; }
      @media(max-width:800px){
        [data-testid="stPopoverBody"]{right:8px!important;top:64px!important;width:calc(100vw - 16px)!important;max-width:calc(100vw - 16px)!important;}
      }
    </style>
    """, unsafe_allow_html=True)

    with st.popover(f"🔔 {len(rows)}", use_container_width=False):
        st.markdown(
            f"<div style='display:flex;align-items:center;justify-content:space-between'>"
            f"<span style='font-size:17px;font-weight:900;color:#edf4fc'>🔔 Alerts</span>"
            f"<span style='font-size:10px;color:#18df82'>{len(rows)} active/recent</span></div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='b4-section'>Active Alerts</div>", unsafe_allow_html=True)
        if rows:
            for row in rows:
                sev = row["severity"]
                dot = "#18df82" if sev in {"INFO", "LOW"} else "#ff3038" if sev in {"CRITICAL", "HIGH", "STRONG"} else "#ffb21c"
                st.markdown(
                    f"<div class='b4-event'><div class='b4-event-main'>"
                    f"<span style='color:{dot}'>●</span> {html.escape(row['symbol'])}"
                    f"<span style='float:right;color:#8194ad;font-size:9px'>{html.escape(row['timestamp'])}</span>"
                    f"</div><div class='b4-event-meta'>{html.escape(row['rule'])} · {html.escape(row['message'])}</div></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No active/recent alerts.")

        with st.expander("⚙ Alert Configuration", expanded=True):
            # Keep the configuration header compact; detailed rule editors open
            # only when a user selects a specific rule. This prevents six
            # always-expanded editor rows from consuming the drawer height.
            a, b, c = st.columns([1.15, 1.0, 1.35])
            with a:
                enabled = st.toggle("Sound", value=enabled, key="sdl_alert_sound_enabled")
            with b:
                tone = st.selectbox(
                    "Tone", ["soft", "single", "double"],
                    index=["soft", "single", "double"].index(tone),
                    key="sdl_alert_sound_tone",
                    label_visibility="collapsed",
                )
            with c:
                volume = st.slider(
                    "Volume", 0.05, 1.0, volume, 0.05,
                    key="sdl_alert_sound_volume",
                    label_visibility="collapsed",
                )
            st.components.v1.html(
                sound_html(
                    SoundSettings(enabled=enabled, volume=volume, tone=tone),
                    trigger=False, nonce="sdl-audio-control"
                ),
                height=42, scrolling=False,
            )
            st.caption("Sound is optional. Test Sound requires one explicit browser gesture before automatic alert playback can be attempted.")

            edited: list[dict[str, Any]] = []
            for idx, rule in enumerate(current_rules):
                summary = f"{rule['field']} {rule['operator']} {float(rule['value']):g}"
                state_icon = "●" if rule["enabled"] else "○"
                sound_icon = "🔊" if rule["sound"] else "🔇"
                label = f"{state_icon} {rule['name']}  ·  {summary}  {sound_icon}"
                with st.expander(label, expanded=False):
                    r1, r2 = st.columns([1.2, 0.8])
                    with r1:
                        rule_enabled = st.toggle(
                            "Enabled", value=bool(rule["enabled"]),
                            key=f"sdl_rule_enabled_{idx}",
                        )
                    with r2:
                        rule_sound = st.toggle(
                            "Sound", value=bool(rule["sound"]),
                            key=f"sdl_rule_sound_{idx}",
                        )
                    c1, c2, c3 = st.columns([1.5, .7, .85])
                    with c1:
                        field = st.selectbox(
                            "Field", FIELDS,
                            index=FIELDS.index(rule["field"]),
                            key=f"sdl_rule_field_{idx}",
                        )
                    with c2:
                        op = st.selectbox(
                            "Op", OPERATORS,
                            index=OPERATORS.index(rule["operator"]),
                            key=f"sdl_rule_op_{idx}",
                        )
                    with c3:
                        value = st.number_input(
                            "Threshold", value=float(rule["value"]), step=1.0,
                            key=f"sdl_rule_value_{idx}",
                        )
                    edited.append({
                        **rule, "enabled": rule_enabled, "sound": rule_sound,
                        "field": field, "operator": op, "value": float(value),
                    })

            if st.button("↺ Reset approved defaults", key="sdl_reset_alert_rules", use_container_width=False):
                edited = [dict(x) for x in DEFAULT_RULES]
                for idx, rule in enumerate(edited):
                    st.session_state[f"sdl_rule_enabled_{idx}"] = bool(rule["enabled"])
                    st.session_state[f"sdl_rule_sound_{idx}"] = bool(rule["sound"])
                    st.session_state[f"sdl_rule_field_{idx}"] = rule["field"]
                    st.session_state[f"sdl_rule_op_{idx}"] = rule["operator"]
                    st.session_state[f"sdl_rule_value_{idx}"] = float(rule["value"])
                st.rerun()
            current_rules = edited

        with st.expander("📜 Alert History", expanded=False):
            st.caption("Persistent alert history remains in the SQLite alert store.")

        # Best-effort automatic announcement. Browser policy may still require
        # one explicit Test Sound/Enable gesture; the visual alert is never muted.
        if new_alert and enabled:
            st.components.v1.html(sound_html(SoundSettings(enabled=True, volume=volume, tone=tone), trigger=True, nonce="sdl-alert-event"), height=1, scrolling=False)

    return {"enabled": enabled, "volume": volume, "tone": tone, "rules": current_rules}
