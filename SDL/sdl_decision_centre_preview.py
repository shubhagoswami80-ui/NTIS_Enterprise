from __future__ import annotations
from pathlib import Path
import time
import pandas as pd
import streamlit as st

import config as sdl_config
import pipeline as sdl_pipeline
from config import EVENT_CSV, STATE_JSON
from pipeline import discover_historical_snapshots, process_snapshot, replay_trading_date
from prediction_engine import build_current_predictions, factor_labels
from source_loader import parse_observation_timestamp
from storage import load_events, load_state

st.set_page_config(page_title="NTIS SDL — Decision Centre", page_icon="SDL",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root{--navy:#081630;--navy2:#18366f;--ink:#17233f;--muted:#6d778a;--page:#f5f7fb;
--line:#e1e6ee;--green:#137c43;--greenbg:#eaf7ef;--red:#b4232c;--redbg:#fff0f1;
--amber:#966300;--amberbg:#fff7df;--slate:#596579;--slatebg:#f1f4f8}
.stApp{background:var(--page);color:var(--ink)}
.block-container{max-width:1480px;padding:18px 22px 34px}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:18px 12px}
.hero{background:linear-gradient(110deg,var(--navy),#102653 65%,var(--navy2));color:#fff;
border-radius:15px;padding:18px 22px;margin:4px 0 14px;min-height:72px;box-shadow:0 8px 25px #07163022}
.hero-title{font-size:27px;font-weight:850}.hero-sub{font-size:12px;opacity:.78;margin-top:4px}
.hero-meta{text-align:right;font-size:12px;line-height:1.6}.live{color:#63e19a;font-weight:850}
.brand-mark{width:44px;height:44px;border-radius:12px;background:#eef2fb;color:#19366f;
display:flex;align-items:center;justify-content:center;font-weight:900;font-size:15px}
.brand-name{font-size:18px;font-weight:850;margin-top:10px}.brand-sub,.nav-note{font-size:10px;color:#7b8494;line-height:1.5}
.nav-label{font-size:9px;letter-spacing:.14em;font-weight:850;color:#8b93a3;margin:24px 0 8px}
.nav-note{border-top:1px solid var(--line);padding-top:15px;margin-top:20px}
.section{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 18px;margin:12px 0;
box-shadow:0 3px 13px #13234309}.title{font-size:18px;font-weight:850}.sub{font-size:12px;color:var(--muted);margin:3px 0 10px}
.priority{background:linear-gradient(110deg,#07152f,#142f64);color:#fff;border-radius:14px;padding:16px 18px;margin:12px 0 0}
.priority-title{font-size:20px;font-weight:850}.priority-sub{font-size:12px;opacity:.78;margin-top:3px}
.metric{background:#fbfcff;border:1px solid var(--line);border-radius:11px;padding:11px 13px;min-height:76px}
.ml{font-size:10px;font-weight:850;letter-spacing:.07em;color:#778196}.mv{font-size:25px;font-weight:850;margin-top:2px}
.mf{font-size:10px;color:#8991a1}.strip{background:#f8faff;border:1px solid #dfe5f1;border-radius:9px;
padding:10px 12px;font-size:11px;color:#5d687c;margin:9px 0}
.badge{display:inline-block;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:850;white-space:nowrap}
.green{background:var(--greenbg);color:var(--green);border:1px solid #b9dfc8}
.red{background:var(--redbg);color:var(--red);border:1px solid #efc2c5}
.amber{background:var(--amberbg);color:var(--amber);border:1px solid #efd99c}
.slate{background:var(--slatebg);color:var(--slate);border:1px solid #dce2eb}
.blue{background:#eef2ff;color:#3155b8;border:1px solid #d5ddff}
.stock-logo{width:27px;height:27px;border-radius:7px;object-fit:contain;background:#fff;border:1px solid #e1e5ed;padding:3px}
.timestamp{font-variant-numeric:tabular-nums;font-weight:750;color:#33405a}
table.sdlq{width:100%;border-collapse:separate;border-spacing:0 6px;font-size:12px}
table.sdlq th{font-size:10px;color:#7a8496;text-align:left;letter-spacing:.06em;padding:6px}
table.sdlq td{padding:9px 7px;background:#fff;border-top:1px solid #edf0f4;border-bottom:1px solid #edf0f4}
table.sdlq td:first-child{border-left:1px solid #edf0f4;border-radius:8px 0 0 8px}
table.sdlq td:last-child{border-right:1px solid #edf0f4;border-radius:0 8px 8px 0}
.inspector{background:#fbfcff;border:1px solid var(--line);border-radius:11px;padding:13px}
.factor{display:flex;justify-content:space-between;padding:10px 2px;border-bottom:1px solid #edf0f4;font-size:12px}
.footer{border-top:1px solid var(--line);margin-top:18px;padding-top:11px;font-size:10px;color:#818a9b;display:flex;justify-content:space-between}
@media(max-width:800px){.block-container{padding:8px}.hero-title{font-size:19px}.hero-meta{font-size:9px}.section{padding:11px}.mv{font-size:18px}}
</style>
""", unsafe_allow_html=True)

def ts(p):
    try: return parse_observation_timestamp(p)
    except Exception:
        try: return pd.Timestamp.fromtimestamp(Path(p).stat().st_mtime)
        except Exception: return pd.NaT

def files(day=None):
    try: x=[Path(p) for p in discover_historical_snapshots(day)]
    except Exception: return []
    return [p for p,_ in sorted([(p,ts(p)) for p in x if pd.notna(ts(p))],key=lambda z:(z[1],str(z[0]).lower()))]

def frozen_base(df):
    if df.empty or "Symbol" not in df.columns:return {}
    r={}
    for _,x in df.drop_duplicates("Symbol").iterrows():
        s=str(x.get("Symbol","")).strip().upper()
        o=pd.to_numeric(x.get("daily_open_reference"),errors="coerce")
        q=pd.to_numeric(x.get("opening_straddle_premium"),errors="coerce")
        if s and pd.notna(o) and pd.notna(q) and q>0:r[s]={"open_price":float(o),"opening_straddle_premium":float(q)}
    return r

def candidates(df):
    if df is None or df.empty:return pd.DataFrame()
    return build_current_predictions(df,frozen_base(df))

def bucket(r):
    if bool(r.get("factual_breakout",False)):return "Breakout"
    s=str(r.get("strength_label","")).upper()
    p=float(r.get("progress",0) or 0)
    d=str(r.get("direction_label","")).upper()
    if "WAIT" in s:return "Wait"
    if p>=75:return "Approaching"
    if s=="DEVELOPING":return "Developing"
    return "Bullish" if d=="BULLISH" else "Bearish"

def apply_filters(df, key):
    if df.empty:
        return df
    c1,c2,c3=st.columns([1.1,1.35,1.0])
    with c1:
        decision=st.selectbox("Decision",["All","Bullish","Bearish","Developing","Wait","Approaching","Breakout"],key=f"{key}_decision")
    with c2:
        progress=st.selectbox("Straddle Progress",["All","<25%","25–50%","50–70%","≥70%","≥75%","100%+"],key=f"{key}_progress")
    with c3:
        strength=st.selectbox("Strength",["All","Strong","Developing","Wait"],key=f"{key}_strength")
    out=df.copy()
    if decision!="All": out=out[out.apply(bucket,axis=1).eq(decision)]
    p=pd.to_numeric(out.get("progress",pd.Series(index=out.index,dtype=float)),errors="coerce").fillna(-1)
    if progress=="<25%": out=out[p<25]
    elif progress=="25–50%": out=out[(p>=25)&(p<50)]
    elif progress=="50–70%": out=out[(p>=50)&(p<70)]
    elif progress=="≥70%": out=out[p>=70]
    elif progress=="≥75%": out=out[p>=75]
    elif progress=="100%+": out=out[p>=100]
    if strength!="All": out=out[out.strength_label.astype(str).str.upper().eq(strength.upper())]
    return out

def first_seen(r):
    for k in ("first_seen_timestamp","first_detection_timestamp","trigger_timestamp","decision_timestamp","observation_timestamp"):
        x=pd.to_datetime(r.get(k),errors="coerce")
        if pd.notna(x): return x
    return pd.NaT

def selected_detail(df, key):
    if df.empty or "symbol" not in df.columns: return
    symbols=[str(x).upper() for x in df["symbol"].dropna().tolist()]
    if not symbols: return
    symbol=st.selectbox("Selected stock",symbols,key=f"{key}_stock")
    r=df[df.symbol.astype(str).str.upper().eq(symbol)].iloc[0]
    progress=float(pd.to_numeric(r.get("progress"),errors="coerce") or 0)
    direction=str(r.get("direction_label","")).upper()
    strength=str(r.get("strength_label","—"))
    stage=str(r.get("stage","—"))
    frozen=pd.to_numeric(r.get("opening_straddle_premium"),errors="coerce")
    openp=pd.to_numeric(r.get("daily_open_reference"),errors="coerce")
    approach=(openp+frozen) if direction=="BULLISH" and pd.notna(openp) and pd.notna(frozen) else ((openp-frozen) if direction=="BEARISH" and pd.notna(openp) and pd.notna(frozen) else float("nan"))
    dclass="green" if direction=="BULLISH" else "red" if direction=="BEARISH" else "slate"
    st.markdown('<div class="section"><div class="title">SELECTED DECISION · '+symbol+'</div><div class="sub">Immediate detail from the existing SDL decision output.</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="priority"><div class="priority-title">{logo(symbol)} {symbol} · <span class="badge {dclass}">{direction or "—"}</span> · {strength}</div><div class="priority-sub">Stage: <b>{stage}</b> · First detected: <b>{time_text(first_seen(r))}</b> · Updated: <b>{time_text(r.get("observation_timestamp"))}</b></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="section"><div class="title">STRADDLE PROGRESSION</div>',unsafe_allow_html=True)
    pos=min(max(progress,0),100)
    st.markdown(f'<div style="position:relative;height:46px;margin:12px 4px 4px"><div style="position:absolute;left:0;right:0;top:19px;height:8px;background:#e5e9f0;border-radius:8px"></div><div style="position:absolute;left:0;top:19px;width:{pos}%;height:8px;background:#3155b8;border-radius:8px"></div><div style="position:absolute;left:{min(pos,100)}%;top:11px;width:22px;height:22px;margin-left:-11px;border-radius:50%;background:#fff;border:4px solid #3155b8"></div><span style="position:absolute;left:0;top:0;font-size:9px;font-weight:800">25%</span><span style="position:absolute;left:33%;top:0;font-size:9px;font-weight:800">50%</span><span style="position:absolute;left:66%;top:0;font-size:9px;font-weight:800">75%</span><span style="position:absolute;right:0;top:0;font-size:9px;font-weight:800">100%</span></div>',unsafe_allow_html=True)
    m1,m2,m3,m4=st.columns(4)
    next_level="100% Breakout" if progress>=75 else "75%" if progress>=50 else "50%" if progress>=25 else "25%"
    m1.metric("Current",f"{progress:.1f}%"); m2.metric("Next Level",next_level); m3.metric("Approach Price","—" if pd.isna(approach) else f"₹{approach:,.2f}"); m4.metric("Breakout Level","—" if pd.isna(approach) else f"₹{approach:,.2f}")
    st.markdown('</div>',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    a.markdown(f'<div class="metric"><div class="ml">STRENGTH</div><div class="mv">{pd.to_numeric(r.get("strength"),errors="coerce") if pd.notna(pd.to_numeric(r.get("strength"),errors="coerce")) else "—"}</div><div class="mf">{strength}</div></div>',unsafe_allow_html=True)
    b.markdown(f'<div class="metric"><div class="ml">STAGE</div><div class="mv" style="font-size:18px">{stage}</div><div class="mf">Existing SDL stage</div></div>',unsafe_allow_html=True)
    move=pd.to_numeric(r.get("signed_price_move_pct"),errors="coerce")
    c.markdown(f'<div class="metric"><div class="ml">MOMENTUM / PRICE</div><div class="mv">{pct(move)}</div><div class="mf">As of {time_text(r.get("observation_timestamp"),False)}</div></div>',unsafe_allow_html=True)
    factors=r.get("factors",[]) or []
    if factors:
        st.markdown('<div class="section"><div class="title">CONFIRMATION</div>',unsafe_allow_html=True)
        for f in factors:
            col="#137c43" if f.state=="SUPPORT" else "#b4232c" if f.state=="CONTRADICT" else "#7b8494"
            st.markdown(f'<div class="factor"><span>{f.label}</span><b style="color:{col}">{f.state}</b></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

def pct(v):
    x=pd.to_numeric(v,errors="coerce")
    return "—" if pd.isna(x) else f"{x:+.2f}%"

def time_text(v,date=True):
    x=pd.to_datetime(v,errors="coerce")
    return "—" if pd.isna(x) else x.strftime("%d %b %Y, %H:%M:%S" if date else "%H:%M:%S")

def logo(s):
    s=str(s).upper().strip()
    if not s or s == "NAN":
        return '<span class="stock-logo" style="display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;color:#6d778a">—</span>'
    safe=s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
    # Attempt the original TradingView logo without ever showing a browser
    # broken-image glyph; initials remain visible as the safe fallback.
    return (f'<span class="stock-logo" title="{safe}" aria-label="{safe} logo" '
            f'style="display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:8px;font-weight:850;color:#19366f;'
            f'background:#fff url(https://s3-symbol-logo.tradingview.com/{s.lower()}.svg) '
            f'center/contain no-repeat;">{safe[:4]}</span>')

def badge(r):
    d=str(r.get("direction_label","")).upper(); b=bucket(r); s=str(r.get("strength_label","")).upper()
    if b=="Breakout": c="green" if d=="BULLISH" else "red"; t=f"{d.title()} · BREAKOUT"
    elif b in ("Approaching","Developing"): c="amber"; t=f"{d.title()} · {b.upper()}"
    elif b=="Wait": c="slate"; t=f"{d.title()} · WAIT"
    else: c="green" if d=="BULLISH" else "red"; t=f"{d.title()} · {s}"
    return f'<span class="badge {c}">{t}</span>'

def queue(df):
    if df.empty:return '<div class="strip">No qualified decisions for this snapshot.</div>'
    rows=[]
    for i,(_,r) in enumerate(df.iterrows(),1):
        price=pd.to_numeric(r.get("signed_price_move_pct"),errors="coerce")
        pc="" if pd.isna(price) else ("color:#137c43;font-weight:850" if price>0 else "color:#b4232c;font-weight:850")
        br=bool(r.get("factual_breakout",False))
        rows.append(f"""<tr><td>{i}</td><td>{logo(r.get("symbol"))} <b>{str(r.get("symbol")).upper()}</b></td>
<td>{badge(r)}</td><td style="{pc}">{pct(price)}</td><td><b>{float(r.get("progress",0)):.1f}%</b></td>
<td>{r.get("stage","—")}</td><td><span class="badge blue">{r.get("strength_label","—")}</span></td>
<td><b>{float(r.get("strength",0)):.0f}</b></td><td style="color:#137c43;font-weight:850">{'YES' if br else '—'}</td>
<td class="timestamp">{time_text(r.get("observation_timestamp"),False)}</td></tr>""")
    return '<div style="overflow-x:auto"><table class="sdlq"><thead><tr><th>#</th><th>STOCK</th><th>DECISION</th><th>PRICE MOVE</th><th>STRADDLE</th><th>STAGE</th><th>CONFIRMATION</th><th>STRENGTH</th><th>BREAKOUT</th><th>TIME</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

def metrics(df,stamp):
    vals=[len(df),int(df.direction_label.eq("BULLISH").sum()) if not df.empty else 0,
          int(df.direction_label.eq("BEARISH").sum()) if not df.empty else 0,
          int(df.strength_label.eq("STRONG").sum()) if not df.empty else 0,
          int(df.factual_breakout.sum()) if not df.empty else 0]
    for c,(l,v) in zip(st.columns(5),zip(["QUALIFIED","BULLISH","BEARISH","STRONG","BREAKOUT"],vals)):
        c.markdown(f'<div class="metric"><div class="ml">{l}</div><div class="mv">{v}</div><div class="mf">As of {time_text(stamp,False)}</div></div>',unsafe_allow_html=True)

def run_live(path,stamp):
    try:
        result=process_snapshot(path,stamp)
        frames=[x for x in result if isinstance(x,pd.DataFrame)] if isinstance(result,tuple) else [result]
        # Existing app uses the second returned dataframe as the current snapshot.
        df=frames[1] if len(frames)>1 else (frames[0] if frames else pd.DataFrame())
        return candidates(df)
    except Exception:
        return pd.DataFrame()

# Sidebar
with st.sidebar:
    st.markdown('<div class="brand-mark">SDL</div><div class="brand-name">NTIS SDL</div>'
                '<div class="brand-sub">Intraday Straddle Breakout<br>Decision Centre</div>',unsafe_allow_html=True)
    st.markdown('<div class="nav-label">NAVIGATION</div>',unsafe_allow_html=True)
    page=st.radio("Navigation",["Decision Board","Replay","Inspector","Historical Evidence","Settings"],
                  label_visibility="collapsed",key="page")
    st.markdown('<div class="nav-note"><b>Preview</b><br>Port 8587<br><br>Production 8504 untouched.<br>'
                'Decision engine remains the existing SDL implementation.</div>',unsafe_allow_html=True)

today=pd.Timestamp.now().date().isoformat()
today_files=files(today)
live_path=max(today_files,key=ts) if today_files else None
live_ts=ts(live_path) if live_path else pd.NaT
live=candidates(pd.DataFrame())

if live_path is not None:
    live=run_live(live_path,live_ts)

st.markdown(f"""<div class="hero"><div style="display:flex;justify-content:space-between;gap:20px;align-items:center">
<div><div class="hero-title">NTIS SDL — Intraday Decision Centre</div>
<div class="hero-sub">Existing SDL decision engine · evidence-driven priority · presentation layer only</div></div>
<div class="hero-meta"><div class="live">● LIVE</div><div>As of: <b>{time_text(live_ts)}</b></div>
<div>Timestamp retained on every decision</div></div></div></div>""",unsafe_allow_html=True)

if page=="Decision Board":
    st.markdown('<div class="priority"><div class="priority-title">★ TOP PRIORITY · LIVE DECISION BOARD</div><div class="priority-sub">One trader view: priority opportunities first, then the full qualified live queue.</div></div>',unsafe_allow_html=True)
    metrics(live,live_ts)
    st.markdown(f'<div class="strip"><b>As of:</b> <span class="timestamp">{time_text(live_ts)}</span> · First Seen remains immutable when provided by the existing decision record.</div>',unsafe_allow_html=True)
    visible=apply_filters(live,"board_filter")
    top=visible.sort_values(["factual_breakout","strength","progress"],ascending=[False,False,False]).head(5) if not visible.empty else visible
    st.markdown('<div class="section"><div class="title">TOP PRIORITY NOW</div><div class="sub">Highest-strength members of the same qualified SDL universe.</div>',unsafe_allow_html=True)
    st.markdown(queue(top),unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="section"><div class="title">LIVE QUEUE</div><div class="sub">Full qualified universe for the current completed evidence bundle.</div>',unsafe_allow_html=True)
    st.markdown(queue(visible),unsafe_allow_html=True)
    selected_detail(visible,"board_detail")
    st.markdown('</div>',unsafe_allow_html=True)

elif page=="Replay":
    st.markdown('<div class="section"><div class="title">HISTORICAL REPLAY</div>'
                '<div class="sub">Trading day and exact snapshot time. Existing replay implementation is used; no later data is introduced.</div>',unsafe_allow_html=True)
    allf=files()
    days=sorted({ts(p).date().isoformat() for p in allf if pd.notna(ts(p))},reverse=True)
    if days:
        day=st.date_input("Trading day",pd.Timestamp(days[0]).date(),key="replay_day")
        dayf=files(day.isoformat())
        times=[ts(p) for p in dayf]
        if times:
            label=st.selectbox("Snapshot time",[t.strftime("%H:%M:%S") for t in times],key="replay_time")
            selected=dayf[[t.strftime("%H:%M:%S") for t in times].index(label)]
            if st.button("Replay selected snapshot",type="primary"):
                try:
                    with st.status(f"Preparing replay {day.strftime('%d %b %Y')}…") as s:
                        replay_trading_date(day.isoformat())
                        _,rdf,rts=process_snapshot(selected,ts(selected))
                        st.session_state["replay_df"]=rdf
                        st.session_state["replay_ts"]=rts
                        s.update(label=f"Replay ready · {label}",state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Replay failed: {e}")
    rdf=st.session_state.get("replay_df",pd.DataFrame())
    if isinstance(rdf,pd.DataFrame) and not rdf.empty:
        rp=candidates(rdf); rts=st.session_state.get("replay_ts",pd.NaT)
        st.markdown(f'<div class="strip"><b>Replay boundary:</b> <span class="timestamp">{time_text(rts)}</span>'
                    ' · Later observations cannot upgrade this result.</div>',unsafe_allow_html=True)
        st.markdown(queue(apply_filters(rp,"replay_filter")),unsafe_allow_html=True)
    else: st.info("Select a trading day and snapshot time, then load Replay.")
    st.markdown('</div>',unsafe_allow_html=True)

elif page=="Inspector":
    src=live
    if isinstance(st.session_state.get("replay_df"),pd.DataFrame) and not st.session_state["replay_df"].empty:
        src=candidates(st.session_state["replay_df"])
    st.markdown('<div class="section"><div class="title">DECISION INSPECTOR</div>'
                '<div class="sub">Detailed evidence for an already-qualified decision. No new scoring is performed.</div>',unsafe_allow_html=True)
    if src.empty: st.info("No qualified decision available.")
    else:
        sym=st.selectbox("Stock",src.symbol.tolist(),key="inspect_symbol")
        r=src[src.symbol.eq(sym)].iloc[0]
        c="green" if str(r.direction_label).upper()=="BULLISH" else "red"
        st.markdown(f'<div class="inspector"><div style="font-size:20px;font-weight:850">{logo(r.symbol)} {r.symbol}</div>'
                    f'<div style="margin-top:6px"><span class="badge {c}">{r.decision}</span></div>'
                    f'<div class="sub" style="margin-top:8px">Timestamp: <span class="timestamp">{time_text(r.get("observation_timestamp"))}</span></div></div>',unsafe_allow_html=True)
        a,b,c1,d=st.columns(4)
        a.metric("Price Move",pct(r.signed_price_move_pct)); b.metric("Straddle Progress",f"{r.progress:.1f}%")
        c1.metric("Strength",f"{r.strength:.0f}"); d.metric("Breakout","YES" if r.factual_breakout else "NO")
        st.markdown('<div class="section"><div class="title">Confirmation Factors</div>',unsafe_allow_html=True)
        for f in r.get("factors",[]) or []:
            icon="✓" if f.state=="SUPPORT" else "!" if f.state=="CONTRADICT" else "•"
            col="color:#137c43" if f.state=="SUPPORT" else "color:#b4232c" if f.state=="CONTRADICT" else "color:#7b8494"
            st.markdown(f'<div class="factor"><span>{f.label}</span><b style="{col}">{icon} {f.state} · {f.weight}</b></div>',unsafe_allow_html=True)
        try: st.caption(" · ".join(factor_labels(r.to_dict())))
        except Exception: pass
        st.markdown('</div>',unsafe_allow_html=True)
        # Preserve raw evidence values when present in the decision row.
        evidence=[("Futures OI",r.get("futures_oi")),("CE OI",r.get("ce_oi_chg_pct")),
                  ("PE OI",r.get("pe_oi_chg_pct")),("PE−CE OI",r.get("pe_minus_ce_oi_chg")),
                  ("PCR",r.get("pcr_chg_pct")),("IV",r.get("iv_chg_pct"))]
        cols=st.columns(3)
        for col,(lab,val) in zip(cols*2,evidence):
            col.metric(lab,"—" if pd.isna(pd.to_numeric(val,errors="coerce")) else f"{float(val):+.2f}")
    st.markdown('</div>',unsafe_allow_html=True)

elif page=="Historical Evidence":
    st.markdown('<div class="section"><div class="title">HISTORICAL EVIDENCE</div>'
                '<div class="sub">Factual historical evidence only; it never feeds information backward into Live or Replay.</div>',unsafe_allow_html=True)
    ev=load_events(EVENT_CSV)
    if ev is None or ev.empty: st.info("No historical evidence records available.")
    else:
        ev=ev.copy()
        if "observation_timestamp" in ev:
            ev["observation_timestamp"]=pd.to_datetime(ev["observation_timestamp"],errors="coerce")
            ev["observation_timestamp"]=ev["observation_timestamp"].dt.strftime("%d %b %Y, %H:%M:%S")
        keep=[c for c in ["observation_timestamp","symbol","direction","price_chg_pct","breakout_distance","strength"] if c in ev.columns]
        st.dataframe(ev[keep].sort_values("observation_timestamp",ascending=False) if keep else ev,
                     width="stretch",hide_index=True)
    st.markdown('</div>',unsafe_allow_html=True)

else:
    st.markdown('<div class="section"><div class="title">SETTINGS</div>'
                '<div class="sub">Administrator settings. Source location is intentionally absent from Live/Top Priority.</div>',unsafe_allow_html=True)
    root=st.text_input("Active source data folder",str(getattr(sdl_pipeline,"INTRADAY_SOURCE_ROOT","")))
    if st.button("Apply source folder",type="primary"):
        p=Path(root).expanduser().resolve()
        sdl_pipeline.INTRADAY_SOURCE_ROOT=p; sdl_config.INTRADAY_SOURCE_ROOT=p
        st.success("Source folder applied for this SDL application session.")
    st.markdown('<div class="strip"><b>Runtime:</b> Preview 8587 · Production 8504 untouched.<br>'
                '<b>Decision engine:</b> existing SDL pipeline/prediction/replay implementation.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="footer"><span>NTIS SDL · Intraday Straddle Breakout Decision Centre</span>'
            '<span>Timestamped data · Preview 8587 · Production 8504 untouched</span></div>',unsafe_allow_html=True)
