"""Compact B4 Alert Drawer UI for NTIS SDL."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Any
import streamlit as st
import html

try:
    import plotly.graph_objects as go
except Exception:
    go = None
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


def _render_intraday_evidence_chart(chart_df, alert_timestamp=None):
    """Render the alert stock chart using exact point-in-time observations.

    Evidence values are never accumulated here.  Markers are placed on the
    price line at the exact observation where the corresponding Futures or
    option OI value increased versus the immediately preceding observation.
    The tooltip reports the values belonging to that timestamp only.
    """
    if chart_df is None or chart_df.empty:
        st.caption("No point-in-time intraday chart data is available.")
        return

    frame = chart_df.copy()
    frame["Observation"] = __import__("pandas").to_datetime(frame["Observation"], errors="coerce")
    frame = frame.dropna(subset=["Observation", "Close"]).sort_values("Observation").reset_index(drop=True)
    if frame.empty:
        st.caption("No point-in-time intraday chart data is available.")
        return

    if go is None:
        st.line_chart(frame.set_index("Observation")["Close"], height=250, use_container_width=True)
        return

    def _num(series):
        return __import__("pandas").to_numeric(series, errors="coerce")

    fig = go.Figure()
    ohlc_cols = ["Open", "High", "Low", "Close"]
    have_ohlc = all(c in frame.columns and _num(frame[c]).notna().any() for c in ohlc_cols)
    if have_ohlc:
        ohlc = frame.copy()
        for c in ohlc_cols:
            ohlc[c] = _num(ohlc[c])
        ohlc = ohlc.dropna(subset=ohlc_cols)
        if not ohlc.empty:
            fig.add_trace(go.Candlestick(
                x=ohlc["Observation"], open=ohlc["Open"], high=ohlc["High"],
                low=ohlc["Low"], close=ohlc["Close"], name="Price",
                increasing_line_color="#16a085", decreasing_line_color="#ef4444",
                increasing_fillcolor="#16a085", decreasing_fillcolor="#ef4444",
                hovertext=[
                    f"{r['Observation']:%H:%M:%S}<br>O: ₹{r['Open']:,.2f}<br>H: ₹{r['High']:,.2f}<br>L: ₹{r['Low']:,.2f}<br>C: ₹{r['Close']:,.2f}"
                    for _, r in ohlc.iterrows()
                ],
                hoverinfo="text",
            ))
        else:
            have_ohlc = False
    if not have_ohlc:
        fig.add_trace(go.Scatter(
            x=frame["Observation"], y=_num(frame["Close"]),
            mode="lines", name="Price",
            line=dict(width=2),
            hovertemplate="%{x|%H:%M:%S}<br>Price: ₹%{y:,.2f}<extra></extra>",
        ))

    def _marker_trace(column, name, symbol, color, label):
        if column not in frame.columns:
            return
        vals = _num(frame[column])
        prev = vals.shift(1)
        mask = vals.notna() & prev.notna() & (vals > prev)
        points = frame.loc[mask].copy()
        if points.empty:
            return
        evidence = _num(points[column])
        hover = []
        for _, r in points.iterrows():
            ts = r["Observation"]
            value = r[column]
            pct_col = "Futures OI Change %" if column == "Futures OI Change" else "PE-CE OI Change %"
            pct_val = r.get(pct_col)
            pct_text = "—" if pct_val is None or __import__("pandas").isna(pct_val) else f"{float(pct_val):+.2f}%"
            hover.append(
                f"{ts:%H:%M:%S}<br>{label}: {float(value):+,.0f}<br>"
                f"Change % at timestamp: {pct_text}<br>Price: ₹{float(r['Close']):,.2f}<extra></extra>"
            )
        fig.add_trace(go.Scatter(
            x=points["Observation"], y=_num(points["Close"]),
            mode="markers", name=name,
            marker=dict(size=6, symbol=symbol, color=color, line=dict(width=0.6, color="#ffffff")),
            text=hover, hovertemplate="%{text}",
        ))

    # Marker values are the exact observation values; no day-to-date sum is used.
    _marker_trace("Futures OI Change", "Futures increase", "triangle-up", "#22c55e", "Futures OI Change")
    _marker_trace("PE-CE OI Change", "PE−CE OI increase", "diamond", "#f59e0b", "PE−CE OI Change")
    _marker_trace("CE OI Change", "CE OI increase", "circle", "#60a5fa", "CE OI Change")
    _marker_trace("PE OI Change", "PE OI increase", "circle-open", "#f472b6", "PE OI Change")

    # Highest available option-OI-change observation for this chart window.
    if "PE-CE OI Change" in frame.columns:
        opt = _num(frame["PE-CE OI Change"])
        valid = opt.dropna()
        if not valid.empty:
            idx = valid.abs().idxmax()
            r = frame.loc[idx]
            fig.add_trace(go.Scatter(
                x=[r["Observation"]], y=[float(r["Close"])],
                mode="markers", name="Max option OI change",
                marker=dict(size=9, symbol="star", color="#f97316", line=dict(width=0.8, color="#ffffff")),
                hovertemplate=(
                    f"{r['Observation']:%H:%M:%S}<br>"
                    f"MAX option OI change at timestamp: {float(r['PE-CE OI Change']):+,.0f}<br>"
                    f"Price: ₹{float(r['Close']):,.2f}<extra></extra>"
                ),
            ))

    alert_ts = __import__("pandas").to_datetime(alert_timestamp, errors="coerce") if alert_timestamp else __import__("pandas").NaT
    if __import__("pandas").notna(alert_ts):
        nearest_idx = (frame["Observation"] - alert_ts).abs().idxmin()
        r = frame.loc[nearest_idx]
        fig.add_trace(go.Scatter(
            x=[r["Observation"]], y=[float(r["Close"])],
            mode="markers", name="Alert",
            marker=dict(size=10, symbol="star-diamond", color="#ef4444", line=dict(width=1, color="#ffffff")),
            hovertemplate=(
                f"ALERT · {r['Observation']:%H:%M:%S}<br>"
                f"Price: ₹{float(r['Close']):,.2f}<extra></extra>"
            ),
        ))
        fig.add_vline(x=r["Observation"], line_width=1, line_dash="dot", line_color="#ef4444", opacity=0.7)

    if "VWAP" in frame.columns:
        vwap = _num(frame["VWAP"])
        if vwap.notna().any():
            fig.add_trace(go.Scatter(
                x=frame["Observation"], y=vwap, mode="lines", name="VWAP",
                line=dict(width=1.2, dash="dot"),
                hovertemplate="%{x|%H:%M:%S}<br>VWAP: ₹%{y:,.2f}<extra></extra>",
            ))

    fig.update_layout(
        height=300,
        margin=dict(l=38, r=12, t=28, b=32),
        paper_bgcolor="#071321",
        plot_bgcolor="#071321",
        font=dict(size=9, color="#cbd7e7"),
        title=dict(text="Intraday Price · Point-in-Time Evidence", font=dict(size=11), x=0),
        hovermode="x unified",
        hoverdistance=40,
        showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=8)),
        xaxis=dict(
            title=None, tickformat="%H:%M", showgrid=True, gridcolor="#17304b",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            rangeslider=dict(visible=False), hoverformat="%H:%M:%S",
        ),
        yaxis=dict(title=None, showgrid=True, gridcolor="#17304b", tickformat=",.0f"),
        hoverlabel=dict(font_size=9),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    st.caption(
        "Candles use point-in-time OHLC when the cached observation contains OHLC; otherwise the chart falls back to Close. "
        "Markers use the exact observation value at that timestamp, never accumulated day-to-date values. "
        "▲ Futures increase · ◆ option OI increase · ★ max option OI change · red ★ alert."
    )

def render_alert_drawer(events:Iterable[Mapping[str,Any]]=(),*,config:DrawerConfig|None=None,history_events:Iterable[Mapping[str,Any]]|None=None,sound_enabled:bool=False,sound_volume:float=0.35,sound_tone:str="soft",new_alert:bool=False,new_alert_sound:bool=False,rules:list[dict[str,Any]]|None=None,chart_provider=None,news_provider=None,diagnostic:str|None=None)->dict[str,Any]:
    cfg=config or DrawerConfig(); rows=_event_rows(events,cfg.max_events); history_rows=_event_rows(history_events or (),50); current_rules=_safe_rules(rules)
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
        # Daily Catalyst Radar is an on-demand side-panel surface. The dashboard
        # supplies a cached provider so normal LIVE refreshes do not scan news.
        if news_provider is not None:
            with st.expander("📰 Daily Catalyst Radar", expanded=True):
                try:
                    radar = news_provider() or {}
                    items = radar.get("items", []) if isinstance(radar, dict) else []
                    affected = radar.get("affected", []) if isinstance(radar, dict) else []
                    if items:
                        for item in items[:8]:
                            impact = str(item.get("impact") or "NEUTRAL").upper()
                            badge = "🟢" if impact == "POSITIVE" else "🔴" if impact == "NEGATIVE" else "⚪"
                            symbols = ", ".join(str(x) for x in (item.get("affected") or [])[:6])
                            st.markdown(
                                f"<div style='padding:6px 0;border-bottom:1px solid #203653'>"
                                f"<b>{badge} {html.escape(_text(item.get('scope'),'NEWS'))}</b> "
                                f"<span style='float:right;color:#8194ad;font-size:8px'>{_text(item.get('time'),'')}</span>"
                                f"<div style='color:#dbe5f3;font-size:10px;margin-top:2px'>{html.escape(_text(item.get('text'),''))}</div>"
                                f"<div style='color:#8fa5c0;font-size:8px;margin-top:2px'>{html.escape(_text(item.get('source'),'News'))} · "
                                f"Affected: {html.escape(_text(symbols,'market/sector'))}</div></div>",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("No ranked daily market/sector catalysts available right now.")
                    if affected:
                        st.markdown("<div style='margin-top:7px;color:#9fb1c7;font-size:9px;font-weight:800'>AFFECTED STOCKS</div>", unsafe_allow_html=True)
                        for row in affected[:10]:
                            chg=row.get("price_change")
                            chg_text="—" if chg is None else f"{float(chg):+.2f}%"
                            cls="#18df82" if chg is not None and float(chg)>0 else "#ff5b6e" if chg is not None and float(chg)<0 else "#9fb1c7"
                            st.markdown(
                                f"<div style='padding:4px 0;border-bottom:1px solid #172b43;font-size:9px'>"
                                f"<b>{html.escape(_text(row.get('symbol'),''))}</b> <span style='color:{cls};font-weight:800'>{chg_text}</span>"
                                f"<div style='color:#8194ad;font-size:8px'>{html.escape(_text(row.get('reason'),'Catalyst context'))}</div></div>",
                                unsafe_allow_html=True,
                            )
                except Exception as exc:
                    st.caption(f"Catalyst radar unavailable: {type(exc).__name__}: {exc}")

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
            if history_rows:
                for row in history_rows:
                    st.markdown(f"<div style='padding:4px 0;border-bottom:1px solid #203653'><b>{row["symbol"]}</b> <span style='color:#8194ad;font-size:9px'>{row["rule"]}</span><span style='float:right;color:#8194ad;font-size:9px'>{row["timestamp"]}</span><div style='color:#cbd7e7;font-size:10px'>{row["message"]}</div></div>",unsafe_allow_html=True)
            else:
                st.caption("No persisted alert history.")
            if diagnostic:
                st.caption(f"Diagnostic: {diagnostic}")
            if history_rows and chart_provider is not None:
                chart_symbols = [row["symbol"] for row in history_rows]
                selected_symbol = st.selectbox("Alert chart", chart_symbols, key="sdl_alert_chart_symbol")
                selected_event = next((e for e in list(history_events or ()) if _text(e.get("symbol"),"UNKNOWN") == selected_symbol), None)
                if selected_event is not None:
                    try:
                        chart_df = chart_provider(selected_event)
                        if chart_df is not None and not chart_df.empty:
                            if "Observation" in chart_df.columns and "Close" in chart_df.columns:
                                _render_intraday_evidence_chart(
                                    chart_df,
                                    selected_event.get("observation_timestamp") or selected_event.get("timestamp"),
                                )
                            else:
                                st.dataframe(chart_df, use_container_width=True, hide_index=True)
                    except Exception as exc:
                        st.caption(f"Chart unavailable: {type(exc).__name__}: {exc}")
        should_sound=bool(new_alert and new_alert_sound and enabled)
    # This audio component is deliberately outside the popover body. It must
    # exist even while the drawer is closed so a new alert can be announced.
    should_sound=bool(new_alert and new_alert_sound and enabled)
    st.components.v1.html(sound_html(SoundSettings(enabled=enabled,volume=volume,tone=tone),trigger=should_sound,nonce="sdl-b41-alert"),height=1)
    return {"enabled":bool(enabled),"volume":float(volume),"tone":str(tone),"rules":current_rules}
