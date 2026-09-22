"""Compact B4 Alert Drawer UI for NTIS SDL."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Any
import streamlit as st
from .alert_sound import SoundSettings, sound_html

DEFAULT_RULES = [
    {"name":"Strong Breakout","field":"Straddle Progress","operator":">=","value":100.0,"enabled":True,"sound":False},
    {"name":"Breakout","field":"Straddle Progress","operator":">=","value":75.0,"enabled":True,"sound":False},
    {"name":"First Alert","field":"Straddle Progress","operator":">=","value":25.0,"enabled":True,"sound":False},
    {"name":"Futures OI Spike","field":"Futures OI Change","operator":">","value":100000.0,"enabled":True,"sound":False},
    {"name":"PCR Extreme","field":"PCR","operator":">","value":3.0,"enabled":True,"sound":False},
    {"name":"High Momentum","field":"Momentum %","operator":">=","value":5.0,"enabled":False,"sound":False},
]
FIELDS=["Futures OI Change","Futures OI Change %","PE − CE OI Change","PCR","Momentum %","Straddle Progress","Price Change %"]
OPERATORS=[">",">=","<","<=","=","!="]

@dataclass(frozen=True)
class DrawerConfig:
    max_events:int=8

def _text(value:Any,fallback:str="—")->str:
    value="" if value is None else str(value).strip()
    return value or fallback

def _safe_rules(rules:Any)->list[dict[str,Any]]:
    if not isinstance(rules,list) or not rules: return [dict(x) for x in DEFAULT_RULES]
    out=[]
    for i,raw in enumerate(rules[:12]):
        if not isinstance(raw,Mapping): continue
        field=str(raw.get("field","PCR")); field=field if field in FIELDS else "PCR"
        op=str(raw.get("operator",">")); op=op if op in OPERATORS else ">"
        try: value=float(raw.get("value",0))
        except Exception: value=0.0
        out.append({"name":_text(raw.get("name"),f"Rule {i+1}"),"field":field,"operator":op,"value":value,"enabled":bool(raw.get("enabled",True)),"sound":bool(raw.get("sound",False))})
    return out or [dict(x) for x in DEFAULT_RULES]

def _event_rows(events:Iterable[Mapping[str,Any]],max_events:int):
    rows=[]
    for event in list(events)[:max(1,int(max_events))]:
        rows.append({"symbol":_text(event.get("symbol"),"UNKNOWN"),"severity":_text(event.get("severity"),"INFO").upper(),"message":_text(event.get("message"),"Alert triggered"),"timestamp":_text(event.get("observation_timestamp") or event.get("timestamp")),"rule":_text(event.get("rule_name"),"Alert rule")})
    return rows

def render_alert_drawer(events:Iterable[Mapping[str,Any]]=(),*,config:DrawerConfig|None=None,sound_enabled:bool=False,sound_volume:float=0.35,sound_tone:str="soft",new_alert:bool=False,new_alert_sound:bool=False,rules:list[dict[str,Any]]|None=None)->dict[str,Any]:
    cfg=config or DrawerConfig(); rows=_event_rows(events,cfg.max_events); current_rules=_safe_rules(rules)
    label=f"🔔 {len(rows)}" if rows else "🔔"
    st.markdown('''<style>
[data-testid="stPopover"] > button{position:fixed!important;right:31vw!important;top:112px!important;z-index:1000000!important;min-width:38px!important;width:38px!important;height:34px!important;padding:0!important;border-radius:8px!important;background:#0d1b2e!important;border:1px solid #3a5a82!important;color:#fff!important;font-size:16px!important;line-height:1!important}
[data-testid="stPopover"] > button svg{display:none!important}
[data-testid="stPopover"] > button span{font-size:0!important}
[data-testid="stPopover"] > button span::before{content:'🔔';font-size:16px!important}
[data-testid="stPopoverBody"]{position:fixed!important;right:14px!important;top:74px!important;left:auto!important;transform:none!important;width:455px!important;max-width:calc(100vw - 28px)!important;max-height:calc(100vh - 90px)!important;overflow-y:auto!important;overflow-x:hidden!important;padding:10px!important;background:#071321!important;border:1px solid #29476e!important;border-radius:10px!important;box-shadow:0 20px 55px rgba(0,0,0,.55)!important;z-index:999999!important}
[data-testid="stPopoverBody"] > div{max-width:none!important}
[data-testid="stPopoverBody"] .stButton button{min-height:28px!important;padding:3px 8px!important;font-size:10px!important}
[data-testid="stPopoverBody"] [data-testid="stExpander"]{margin:6px 0!important;border:1px solid #29476e!important;background:#091729!important}
[data-testid="stPopoverBody"] [data-testid="stExpanderDetails"]{padding:7px 9px!important}
[data-testid="stPopoverBody"] label{font-size:9px!important}
.b41-rule{padding:5px 0 6px;border-bottom:1px solid #1b304c}.b41-rule-cond{color:#9fb1c7;font-size:9px;margin:2px 0 3px 24px}.b41-muted{color:#8fa5c0;font-size:9px}
</style>''',unsafe_allow_html=True)
    with st.popover(label,use_container_width=False):
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:3px'><b style='font-size:15px'>🔔 Alerts</b><span style='font-size:9px;color:#18df82'>{len(rows)} active/recent</span></div>",unsafe_allow_html=True)
        if rows:
            for row in rows:
                st.markdown(f"<div style='padding:5px 0;border-bottom:1px solid #203653'><b>{row['symbol']}</b> <span style='color:#8194ad;font-size:9px'>{row['rule']}</span><span style='float:right;color:#8194ad;font-size:9px'>{row['timestamp']}</span><div style='color:#cbd7e7;font-size:10px'>{row['message']}</div></div>",unsafe_allow_html=True)
        else: st.markdown("<div class='b41-muted' style='padding:3px 0 7px'>No active/recent alerts.</div>",unsafe_allow_html=True)
        with st.expander("⚙ Alert Configuration",expanded=True):
            c1,c2=st.columns([1.35,1])
            with c1: enabled=st.toggle("Enable sound",value=bool(sound_enabled),key="sdl_alert_sound_enabled")
            with c2: tone=st.selectbox("Sound",["soft","single","double"],index=["soft","single","double"].index(sound_tone if sound_tone in {"soft","single","double"} else "soft"),key="sdl_alert_sound_tone")
            volume=st.slider("Volume",0.05,1.0,max(0.05,min(float(sound_volume),1.0)),0.05,key="sdl_alert_sound_volume")
            st.components.v1.html(sound_html(SoundSettings(True,float(volume),tone),test_button=True,nonce="sdl-b41-test"),height=42)
            st.markdown("<div class='b41-muted' style='margin:2px 0 5px'>Threshold rules trigger on a new crossing, not on every refresh.</div>",unsafe_allow_html=True)
            edited=[]
            for idx,rule in enumerate(current_rules):
                st.markdown("<div class='b41-rule'>",unsafe_allow_html=True)
                a,b=st.columns([1.8,.8])
                with a: rule_enabled=st.toggle(rule["name"],value=bool(rule["enabled"]),key=f"sdl_rule_enabled_{idx}")
                with b: rule_sound=st.toggle("Sound",value=bool(rule["sound"]),key=f"sdl_rule_sound_{idx}")
                f,o,v=st.columns([1.55,.7,.75])
                with f: field=st.selectbox("Field",FIELDS,index=FIELDS.index(rule["field"]),key=f"sdl_rule_field_{idx}")
                with o: op=st.selectbox("Op",OPERATORS,index=OPERATORS.index(rule["operator"]),key=f"sdl_rule_op_{idx}")
                with v: value=st.number_input("Value",value=float(rule["value"]),step=1.0,key=f"sdl_rule_value_{idx}")
                st.markdown(f"<div class='b41-rule-cond'>{field} {op} {float(value):g}</div></div>",unsafe_allow_html=True)
                edited.append({**rule,"enabled":bool(rule_enabled),"sound":bool(rule_sound),"field":field,"operator":op,"value":float(value)})
            if st.button("↺ Reset default rules",key="sdl_reset_alert_rules"):
                for idx,rule in enumerate(DEFAULT_RULES):
                    st.session_state[f"sdl_rule_enabled_{idx}"]=bool(rule["enabled"]); st.session_state[f"sdl_rule_sound_{idx}"]=bool(rule["sound"]); st.session_state[f"sdl_rule_field_{idx}"]=rule["field"]; st.session_state[f"sdl_rule_op_{idx}"]=rule["operator"]; st.session_state[f"sdl_rule_value_{idx}"]=float(rule["value"])
                st.rerun()
            current_rules=edited
        with st.expander("📜 Alert History",expanded=False):
            st.caption("History is bounded here; the persistent alert store remains the source of record.")
        should_sound=bool(new_alert and new_alert_sound and enabled)
    # This audio component is deliberately outside the popover body. It must
    # exist even while the drawer is closed so a new alert can be announced.
    should_sound=bool(new_alert and new_alert_sound and enabled)
    st.components.v1.html(sound_html(SoundSettings(enabled=enabled,volume=volume,tone=tone),trigger=should_sound,nonce="sdl-b41-alert"),height=1)
    return {"enabled":bool(enabled),"volume":float(volume),"tone":str(tone),"rules":current_rules}
