from __future__ import annotations
import hashlib
from pathlib import Path
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False, max_entries=16)
def _read_csv(path_text: str, signature: str, nrows: int | None):
    return pd.read_csv(path_text, nrows=nrows)

def _signature(path: Path) -> str:
    s = path.stat()
    return hashlib.sha1(
        f"{path.resolve()}|{s.st_size}|{s.st_mtime_ns}".encode()
    ).hexdigest()

class W73DataStore:
    """W73-owned data + explicit external read-only live CSV."""

    def __init__(self, cfg):
        self.cfg = cfg

    def validation(self) -> pd.DataFrame:
        p = self.cfg.validation_csv
        if not p.exists():
            return pd.DataFrame()
        return _read_csv(str(p), _signature(p), self.cfg.max_rows)

    def live(self) -> pd.DataFrame:
        p = self.cfg.live_input
        if not p or not p.exists() or p.suffix.lower() != ".csv":
            return pd.DataFrame()
        return _read_csv(str(p), _signature(p), self.cfg.max_rows)
