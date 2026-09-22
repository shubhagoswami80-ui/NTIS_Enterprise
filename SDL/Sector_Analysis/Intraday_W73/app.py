from __future__ import annotations
import streamlit as st
from config import W73Config
from data_store import W73DataStore
from strategy import W73Strategy
from views import render_page

def render_intraday_w73_page() -> None:
    cfg = W73Config.from_environment()
    store = W73DataStore(cfg)
    strategy = W73Strategy(store)
    render_page(st, cfg, store, strategy)

def main() -> None:
    st.set_page_config(page_title="NTIS SDL — Intraday W73",
                       page_icon="⚡", layout="wide",
                       initial_sidebar_state="collapsed")
    render_intraday_w73_page()

if __name__ == "__main__":
    main()
