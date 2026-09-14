#!/usr/bin/env python3
"""
Frozen ATM Premium Skew engine.

Input:
- NSE option-chain CSV/XLSX containing strike-level CE/PE fields
- frozen opening-price registry CSV containing symbol, official_open_price,
  fixed_atm_strike, trade_date, and method

The engine:
1. Reads the option-chain snapshot.
2. Uses the registry's fixed_atm_strike; it never recalculates ATM from a
   moving/current price.
3. Selects the matching CE and PE rows at that strike.
4. Calculates:
   Bias % = ((CE LTP - PE LTP) / (CE LTP + PE LTP)) * 100
5. Adds IV, volume, OI and change-in-OI fields when available.
6. Does not estimate Delta or 25-Delta IV.
7. Does not calculate event states; thresholds are reserved for the event layer.
"""

from __future__ import annotations
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
import pandas as pd

ALIASES = {
    "symbol":"symbol", "ticker":"symbol", "underlying":"symbol",
    "strike":"strike", "strike_price":"strike",
    "expiry":"expiry", "expiration":"expiry",
    "ce_ltp":"ce_ltp", "call_ltp":"ce_ltp", "call_last_price":"ce_ltp",
    "pe_ltp":"pe_ltp", "put_ltp":"pe_ltp", "put_last_price":"pe_ltp",
    "ce_iv":"ce_iv", "call_iv":"ce_iv", "pe_iv":"pe_iv", "put_iv":"pe_iv",
    "ce_volume":"ce_volume", "call_volume":"ce_volume",
    "pe_volume":"pe_volume", "put_volume":"pe_volume",
    "ce_oi":"ce_oi", "call_oi":"ce_oi", "pe_oi":"pe_oi", "put_oi":"pe_oi",
    "ce_change_oi":"ce_change_oi", "pe_change_oi":"pe_change_oi",
}

def key(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).strip().lower()).strip("_")

def norm(df):
    used=set(); rename={}
    for c in df.columns:
        t=ALIASES.get(key(c), key(c) or "unnamed")
        if t in used:
            i=2
            while f"{t}_{i}" in used: i+=1
            t=f"{t}_{i}"
        used.add(t); rename[c]=t
    out=df.rename(columns=rename).copy()
    for c in ["symbol","expiry"]:
        if c in out: out[c]=out[c].astype("string").str.strip()
    if "symbol" in out: out["symbol"]=out["symbol"].str.upper()
    if "strike" in out: out["strike"]=pd.to_numeric(out["strike"], errors="coerce")
    return out

def read_any(path):
    return pd.read_csv(path) if path.suffix.lower()==".csv" else pd.read_excel(path)

def num(row, col):
    if col not in row: return None
    v=pd.to_numeric(pd.Series([row[col]]), errors="coerce").iloc[0]
    return None if pd.isna(v) else float(v)

def main(a):
    chain=norm(read_any(Path(a.chain)))
    registry=pd.read_csv(a.registry)
    registry.columns=[key(c) for c in registry.columns]
    required={"symbol","fixed_atm_strike"}
    missing=required-set(registry.columns)
    if missing: raise ValueError("Registry missing: "+", ".join(sorted(missing)))

    rows=[]
    for _, r in registry.iterrows():
        symbol=str(r["symbol"]).strip().upper()
        atm=pd.to_numeric(pd.Series([r["fixed_atm_strike"]]), errors="coerce").iloc[0]
        if pd.isna(atm): continue
        subset=chain[chain.get("symbol", pd.Series(index=chain.index, dtype="string")).astype("string").str.upper()==symbol] if "symbol" in chain else chain
        if "strike" not in subset: continue
        subset=subset[subset["strike"]==float(atm)]
        if subset.empty: continue
        # Accept either already-paired CE/PE columns or NSE side-specific rows.
        row=subset.iloc[0]
        ce=num(row,"ce_ltp"); pe=num(row,"pe_ltp")
        if ce is None or pe is None:
            continue
        denom=ce+pe
        if denom <= 0: continue
        out={
            "calculated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "trade_date": r.get("trade_date"),
            "symbol": symbol,
            "expiry": r.get("expiry"),
            "official_open_price": num(r,"official_open_price"),
            "fixed_atm_strike": float(atm),
            "atm_ce_premium": ce,
            "atm_pe_premium": pe,
            "bias_pct": (ce-pe)/denom*100.0,
            "atm_ce_iv": num(row,"ce_iv"),
            "atm_pe_iv": num(row,"pe_iv"),
            "atm_ce_volume": num(row,"ce_volume"),
            "atm_pe_volume": num(row,"pe_volume"),
            "atm_ce_oi": num(row,"ce_oi"),
            "atm_pe_oi": num(row,"pe_oi"),
            "atm_ce_change_oi": num(row,"ce_change_oi"),
            "atm_pe_change_oi": num(row,"pe_change_oi"),
            "delta_25_ce_iv": None,
            "delta_25_pe_iv": None,
            "status": "CALCULATED",
        }
        rows.append(out)
    out=pd.DataFrame(rows)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output,index=False)
    print(json.dumps({"status":"OK","rows":len(out),"output":a.output}, indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--chain",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--output",required=True)
    main(p.parse_args())
