from __future__ import annotations
import argparse, json, re
from pathlib import Path
import pandas as pd

PREFIX = "Daywise_Price_and_OI_Summary_"

def ts_from_name(path: Path):
    m = re.search(r"_(\d{8})_(\d{6})\.xlsx$", path.name, re.I)
    if not m:
        return pd.NaT
    return pd.to_datetime(m.group(1) + m.group(2), format="%Y%m%d%H%M%S", errors="coerce")

def norm(x):
    return re.sub(r"\s+", " ", str(x).strip().lower())

def find_col(cols, names):
    mp = {norm(c): c for c in cols}
    for n in names:
        if norm(n) in mp:
            return mp[norm(n)]
    return None

def audit_day(source_root: Path, month: str, trading_date: str, symbols: list[str], sample_files: int):
    day = source_root / month / trading_date
    files = sorted(day.glob(PREFIX + "*.xlsx"), key=lambda p: (ts_from_name(p), p.name))
    files = [p for p in files if pd.notna(ts_from_name(p))]
    if not files:
        raise SystemExit(f"NO_SOURCE_FILES: {day}")

    chosen = files[:sample_files]
    rows = []
    file_summary = []

    for path in chosen:
        try:
            df = pd.read_excel(path)
        except Exception as e:
            file_summary.append({"file": path.name, "read_error": str(e)})
            continue

        sym = find_col(df.columns, ["Symbol"])
        high = find_col(df.columns, ["High"])
        low = find_col(df.columns, ["Low"])
        close = find_col(df.columns, ["Close"])
        pchg = find_col(df.columns, ["Price Chg"])
        pchgp = find_col(df.columns, ["Price Chg %"])
        atr = {"file": path.name, "timestamp": str(ts_from_name(path)),
               "rows": len(df), "columns": list(map(str, df.columns)),
               "fields": {"Symbol": sym, "High": high, "Low": low, "Close": close,
                          "Price Chg": pchg, "Price Chg %": pchgp}}
        file_summary.append(atr)

        if not sym:
            continue
        wanted = symbols if symbols else list(df[sym].dropna().astype(str).head(5))
        for s in wanted:
            hit = df[df[sym].astype(str).str.strip().str.upper() == s.strip().upper()]
            if hit.empty:
                continue
            r = hit.iloc[0]
            rows.append({
                "symbol": s,
                "source_timestamp": str(ts_from_name(path)),
                "file": path.name,
                "High": r[high] if high else None,
                "Low": r[low] if low else None,
                "Close": r[close] if close else None,
                "Price Chg": r[pchg] if pchg else None,
                "Price Chg %": r[pchgp] if pchgp else None,
            })

    obs = pd.DataFrame(rows)
    analysis = {}
    if not obs.empty:
        for s, g in obs.groupby("symbol"):
            g = g.sort_values("source_timestamp")
            num = g[["High","Low","Close","Price Chg","Price Chg %"]].apply(pd.to_numeric, errors="coerce")
            analysis[s] = {
                "intervals_observed": len(g),
                "high_monotonic_non_decreasing": bool(num["High"].dropna().is_monotonic_increasing) if num["High"].notna().any() else None,
                "low_monotonic_non_decreasing": bool(num["Low"].dropna().is_monotonic_increasing) if num["Low"].notna().any() else None,
                "high_unique_count": int(num["High"].nunique(dropna=True)),
                "low_unique_count": int(num["Low"].nunique(dropna=True)),
                "close_unique_count": int(num["Close"].nunique(dropna=True)),
                "price_chg_unique_count": int(num["Price Chg"].nunique(dropna=True)),
                "price_chg_pct_unique_count": int(num["Price Chg %"].nunique(dropna=True)),
                "first_last": {
                    "first": g.iloc[0].to_dict(),
                    "last": g.iloc[-1].to_dict(),
                },
            }

    result = {
        "status": "PASS_AUDIT",
        "source_root": str(source_root),
        "month_folder": month,
        "trading_date": trading_date,
        "day_folder": str(day),
        "files_found": len(files),
        "files_sampled": len(chosen),
        "file_summary": file_summary,
        "symbol_analysis": analysis,
        "interpretation_rules": {
            "cumulative_high_signal": "High monotonic non-decreasing across snapshots is evidence consistent with cumulative/session High, not proof.",
            "cumulative_low_signal": "Low monotonic non-decreasing is not sufficient alone; a session Low normally tends to be non-increasing, so inspect actual sequence.",
            "close_series": "Changing Close across source timestamps establishes a point-in-time price series but does not by itself establish candle semantics.",
            "orb_requirement": "Authoritative replay ORB requires a causal price stream with initial-window high/low and later close breakout.",
        },
        "conclusion": "DIAGNOSTIC_ONLY: no strategy or V8 rule is changed by this audit."
    }

    out = Path(__file__).resolve().parents[1] / "07_OUTPUT"
    out.mkdir(parents=True, exist_ok=True)
    (out/"orb_source_capability_audit_v1.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    if not obs.empty:
        obs.to_csv(out/"orb_source_sample_observations.csv", index=False)
    print(json.dumps({
        "status": result["status"],
        "files_found": len(files),
        "files_sampled": len(chosen),
        "symbols_audited": list(analysis),
        "output": str(out/"orb_source_capability_audit_v1.json")
    }, indent=2))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("month")
    ap.add_argument("trading_date")
    ap.add_argument("--source-root", default=r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
    ap.add_argument("--symbol", action="append", dest="symbols", default=[])
    ap.add_argument("--sample-files", type=int, default=12)
    a = ap.parse_args()
    audit_day(Path(a.source_root), a.month, a.trading_date, a.symbols, a.sample_files)
