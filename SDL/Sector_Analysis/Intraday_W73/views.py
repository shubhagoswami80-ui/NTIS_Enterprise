from __future__ import annotations
import html
import pandas as pd

def render_page(st, cfg, store, strategy):
    st.markdown("""
    <style>
    .block-container{max-width:1700px;padding:.55rem .75rem 2rem}
    .w73-title{font-size:clamp(1.05rem,2.2vw,1.65rem);font-weight:750}
    .w73-sub{color:#9aa8bd;font-size:.78rem;margin-bottom:.55rem}
    .w73-card{border:1px solid rgba(148,163,184,.18);border-radius:9px;
      padding:.65rem .72rem;background:rgba(15,23,42,.58);min-height:76px}
    .w73-label{color:#94a3b8;font-size:.69rem;text-transform:uppercase}
    .w73-value{font-size:1.12rem;font-weight:750;margin-top:.12rem}
    .w73-green{color:#22c55e}
    @media(max-width:720px){.block-container{padding:.35rem .45rem 1.2rem}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="w73-title">⚡ NTIS SDL — Intraday W73</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="w73-sub">72.093% frozen historical baseline • '
        'live / replay / historical evidence modular</div>',
        unsafe_allow_html=True)

    base = strategy.baseline()
    if base is None:
        st.error("W73 baseline is missing from 00_BASELINE.")
        return

    c = st.columns(4)
    values = [
        ("Historical rate", f"{base.holdout_rate*100:.3f}%", "w73-green"),
        ("Evidence n", base.holdout_n, ""),
        ("Holdout dates", base.holdout_dates, ""),
        ("Symbols", base.holdout_symbols, ""),
    ]
    for col, (label, value, cls) in zip(c, values):
        with col:
            st.markdown(
                f'<div class="w73-card"><div class="w73-label">{html.escape(str(label))}</div>'
                f'<div class="w73-value {cls}">{html.escape(str(value))}</div></div>',
                unsafe_allow_html=True)

    live = store.live()
    if live.empty:
        st.warning("LIVE INPUT NOT CONNECTED — W73 will not manufacture signals.")
    else:
        matched = strategy.match_live(live, base)
        exact = int(matched["_w73_exact_match"].sum()) if not matched.empty else 0
        st.info(f"Live rows: {len(live)} | Exact W73 matches: {exact}")
        if not matched.empty:
            show = [c for c in ["symbol","timestamp","trade_date",
                                "_w73_match_pct","_w73_exact_match"] if c in matched.columns]
            st.dataframe(matched[show].head(100), width="stretch", hide_index=True)

    with st.expander("Frozen W73 candidate definition"):
        display = pd.DataFrame(
            [{"Feature": str(k), "Frozen value": str(v)}
             for k, v in base.conditions.items()],
            columns=["Feature","Frozen value"])
        st.dataframe(display, width="stretch", hide_index=True)
