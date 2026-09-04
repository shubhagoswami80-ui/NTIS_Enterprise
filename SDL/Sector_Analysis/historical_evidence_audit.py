from pathlib import Path
import pandas as pd
import json

SDL_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SDL_ROOT / "data"
OUT = SDL_ROOT / "Sector_Analysis" / ".sector_intelligence" / "historical_evidence_audit"
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = [
    DATA_ROOT / "output" / "required_evidence",
    DATA_ROOT / "output" / "early_prediction_research" / "snapshot_replay_source.csv",
    DATA_ROOT / "output" / "early_prediction_gate_audit" / "gate_audit_events.csv",
    DATA_ROOT / "output" / "early_prediction_futures_oi_v4_2_controlled" / "first_22_point_in_time_controlled.csv",
    DATA_ROOT / "output" / "tradable_events" / "approaching_breakouts.csv",
    DATA_ROOT / "output" / "tradable_events" / "breakout_events.csv",
    DATA_ROOT / "output" / "continuation_research" / "continuation_research_events.csv",
]

ALIASES = {
    "symbol": ["symbol","Symbol","ticker","Ticker"],
    "date": ["trading_date","Trading Date","date","Date"],
    "timestamp": ["observation_timestamp","Observation Timestamp","timestamp","Timestamp","datetime","Datetime"],
    "direction": ["direction","Direction","side","Side"],
    "price": ["price","Price","current_price","Current Price","cmp","CMP"],
    "price_chg_pct": ["price_chg_pct","Price Chg %","price_change_pct","Price Change %"],
    "oi_chg_pct": ["oi_chg_pct","OI Chg %","OI Change %"],
    "ce_oi_chg_pct": ["ce_oi_chg_pct","CE OI Chg %","Tot CE OI Chg %","CE OI Change %"],
    "pe_oi_chg_pct": ["pe_oi_chg_pct","PE OI Chg %","Tot PE OI Chg %","PE OI Change %"],
    "pe_ce": ["pe_ce","PE-CE","PE minus CE","Tot PE-CE OI Chg","pe_ce_oi_chg"],
    "volume_chg_pct": ["volume_chg_pct","Volume Chg %","Volume Change %"],
    "buildup": ["buildup","Buildup"],
}

def pick(df, names):
    m = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in m:
            return m[n.lower()]
    return None

def read_csv(path):
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as e:
        return pd.DataFrame({"_read_error":[str(e)]})

def inspect(path):
    df = read_csv(path)
    rows = len(df)
    mapped = {k: pick(df,v) for k,v in ALIASES.items()}
    return {
        "source": str(path),
        "exists": path.exists(),
        "rows": rows,
        "columns": len(df.columns),
        "mapped_fields": mapped,
        "has_symbol": mapped["symbol"] is not None,
        "has_timestamp": mapped["timestamp"] is not None,
        "read_error": df["_read_error"].iloc[0] if "_read_error" in df.columns else None,
    }

def main():
    files = []
    for s in SOURCES:
        if s.is_dir():
            files.extend(sorted(s.glob("*.csv")))
        elif s.exists():
            files.append(s)

    inventory = [inspect(p) for p in files]
    pd.DataFrame(inventory).to_csv(OUT / "source_inventory.csv", index=False)

    # Build a compact chronology audit from files that contain symbol/date/timestamp.
    traces = []
    for item in inventory:
        p = Path(item["source"])
        if not item["exists"] or item["read_error"]:
            continue
        df = read_csv(p)
        c = item["mapped_fields"]
        if not c["symbol"] or not c["timestamp"]:
            continue
        t = pd.DataFrame({
            "symbol": df[c["symbol"]].astype("string"),
            "timestamp": pd.to_datetime(df[c["timestamp"]], errors="coerce"),
            "source": p.name,
        })
        t = t.dropna(subset=["symbol","timestamp"])
        if t.empty:
            continue
        traces.append(t.groupby("source").agg(
            rows=("symbol","size"),
            unique_symbols=("symbol","nunique"),
            min_timestamp=("timestamp","min"),
            max_timestamp=("timestamp","max"),
        ).reset_index())

    chronology = pd.concat(traces, ignore_index=True) if traces else pd.DataFrame()
    chronology.to_csv(OUT / "chronology_inventory.csv", index=False)

    summary = {
        "purpose": "Historical evidence audit only; no trading rule or signal is generated.",
        "source_count": len(files),
        "timestamp_traceable_sources": int(sum(x["has_timestamp"] for x in inventory)),
        "symbol_traceable_sources": int(sum(x["has_symbol"] for x in inventory)),
        "next_step": "Use timestamped SDL observations and existing outcome events to perform strict pre-outcome event matching.",
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("AUDIT COMPLETE")
    print("SOURCES:", len(files))
    print("TIMESTAMP-TRACEABLE:", summary["timestamp_traceable_sources"])
    print("SYMBOL-TRACEABLE:", summary["symbol_traceable_sources"])
    print("OUTPUT:", OUT)

if __name__ == "__main__":
    main()
