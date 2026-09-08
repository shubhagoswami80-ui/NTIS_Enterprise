import argparse, json, math
from pathlib import Path
import itertools
import numpy as np
import pandas as pd

HORIZONS = [1, 2, 3, 5, 10, 20]
MIN_OUTCOMES = 30
MIN_DATES = 3
MIN_SYMBOLS = 10
ACCEPT_RATE = 0.80

def norm(s):
    return str(s).strip().lower().replace(" ", "_").replace("%","pct").replace("-","_")

def find_col(df, names):
    cols = {norm(c): c for c in df.columns}
    for n in names:
        if norm(n) in cols:
            return cols[norm(n)]
    return None

def num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col and col in df else pd.Series(np.nan, index=df.index)

def direction_from_price(s):
    return np.where(s > 0, "UP", np.where(s < 0, "DOWN", np.where(s == 0, "FLAT", "")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    base = out.parent
    candidates = list(base.rglob("clean_intraday_timeline.csv"))
    if not candidates:
        raise SystemExit("CLEAN_TIMELINE_NOT_FOUND: run historical_outcome_timeline_integrity_fix.py first")
    timeline_path = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"CLEAN_TIMELINE_FOUND: {timeline_path}")

    df = pd.read_csv(timeline_path, low_memory=False)
    print(f"CLEAN_TIMELINE_ROWS: {len(df)}")

    # Canonical aliases; no inference from fuzzy substrings.
    symbol = find_col(df, ["symbol"])
    day = find_col(df, ["trade_date","trading_date","date"])
    ts = find_col(df, ["timestamp","observation_timestamp"])
    pc = find_col(df, ["price_chg","price_change"])
    pcp = find_col(df, ["price_chg_pct","price_change_pct","price_chg_percent"])
    op = find_col(df, ["open"]); hi = find_col(df, ["high"]); lo = find_col(df, ["low"]); cl = find_col(df, ["close"])

    if not all([symbol, day, ts, pc]):
        raise SystemExit("REQUIRED_PRICE_TIMELINE_FIELDS_MISSING")

    df["symbol"] = df[symbol].astype("string").str.strip().str.upper()
    df["trade_date"] = pd.to_datetime(df[day], errors="coerce").dt.date
    df["timestamp"] = pd.to_datetime(df[ts], errors="coerce")
    df["price_chg"] = num(df, pc)
    df["price_chg_pct"] = num(df, pcp)
    for dest, src in [("open",op),("high",hi),("low",lo),("close",cl)]:
        df[dest] = num(df, src)

    # Evidence columns: exact normalized names only.
    aliases = {
        "ce_num": ["tol_ce_oi_chg","tot_ce_oi_chg"],
        "pe_num": ["tol_pe_oi_chg","tot_pe_oi_chg"],
        "pec_num": ["tol_pe_ce_oi_chg","tot_pe_ce_oi_chg"],
        "ce_pct": ["tol_ce_oi_chg_pct","tot_ce_oi_chg_pct"],
        "pe_pct": ["tol_pe_oi_chg_pct","tot_pe_oi_chg_pct"],
        "pec_pct": ["tol_pe_ce_oi_chg_pct","tot_pe_ce_oi_chg_pct"],
        "fut_num": ["oi_chg"],
        "fut_pct": ["oi_chg_pct"],
        "volume_pct": ["volume_chg_pct","volume_chg"],
        "fut_state": ["fut_state","fut_buildup","buildup"],
        "fut_price_chg": ["fut_direction","fut_price_chg","futures_price_chg"]
    }
    for k, ns in aliases.items():
        c = find_col(df, ns)
        df[k] = num(df, c) if k not in ("fut_state",) else (df[c].astype("string").str.upper().str.strip() if c else pd.Series("", index=df.index, dtype="string"))

    # If futures price change is not explicitly present in canonical cache, do not
    # manufacture it from stock price change.
    # Canonical stock direction is authoritative for stock outcomes.
    # Do not infer stock direction from options or futures.
    df["stock_dir"] = df["price_direction"].astype("string").str.upper().str.strip()
    missing_dir = ~df["stock_dir"].isin(["UP","DOWN","FLAT"])
    df.loc[missing_dir, "stock_dir"] = direction_from_price(df.loc[missing_dir, "price_chg"].to_numpy())

    # Futures direction is already canonicalized upstream. Use it only as an
    # evidence attribute; it never determines the stock outcome.
    df["fut_dir"] = df["fut_direction"].astype("string").str.upper().str.strip()

    # Sequence order and anchor-relative future outcomes.
    df = df.sort_values(["symbol","trade_date","timestamp"], kind="mergesort").reset_index(drop=True)
    g = df.groupby(["symbol","trade_date"], sort=False, group_keys=False)
    for h in HORIZONS:
        df[f"close_t{h}"] = g["close"].shift(-h)
        df[f"pricechg_t{h}"] = g["price_chg"].shift(-h)
        # Anchor-relative return when both closes are present.
        df[f"move_t{h}_pct"] = np.where(
            df["close"].notna() & df[f"close_t{h}"].notna() & (df["close"] != 0),
            (df[f"close_t{h}"] / df["close"] - 1.0) * 100.0,
            np.nan
        )

    # Intraday favorable/adverse excursion over the next 20 observations.
    future_hi = np.full(len(df), np.nan)
    future_lo = np.full(len(df), np.nan)
    for _, idx in g.indices.items():
        ix = np.asarray(idx)
        hh = df.loc[ix, "high"].to_numpy(dtype=float)
        ll = df.loc[ix, "low"].to_numpy(dtype=float)
        for j, pos in enumerate(ix):
            hi_slice = hh[j+1:min(j+21, len(hh))]
            lo_slice = ll[j+1:min(j+21, len(ll))]
            if hi_slice.size and np.isfinite(hi_slice).any():
                future_hi[pos] = np.nanmax(hi_slice)
            if lo_slice.size and np.isfinite(lo_slice).any():
                future_lo[pos] = np.nanmin(lo_slice)
    df["future_hi_20"] = future_hi
    df["future_lo_20"] = future_lo

    # Candidate footprint flags.
    feats = {}
    for name, col in [
        ("CE_NUM_GT500","ce_num"),("CE_NUM_GT1000","ce_num"),
        ("PE_NUM_GT500","pe_num"),("PE_NUM_GT1000","pe_num"),
        ("PECE_NUM_GT500","pec_num"),("PECE_NUM_GT1000","pec_num"),
        ("CE_PCT_GT1","ce_pct"),("CE_PCT_GT2","ce_pct"),
        ("PE_PCT_GT1","pe_pct"),("PE_PCT_GT2","pe_pct"),
        ("PECE_PCT_GT1","pec_pct"),("PECE_PCT_GT2","pec_pct"),
        ("FUT_OI_GT500","fut_num"),("FUT_OI_GT1000","fut_num"),
        ("FUT_PCT_GT1","fut_pct"),("FUT_PCT_GT2","fut_pct"),
        ("VOL_P90","volume_pct"),("VOL_P95","volume_pct")
    ]:
        s = df[col]
        if name.endswith("GT500"): feats[name] = s.abs().gt(500)
        elif name.endswith("GT1000"): feats[name] = s.abs().gt(1000)
        elif name.endswith("GT1"): feats[name] = s.abs().gt(1)
        elif name.endswith("GT2"): feats[name] = s.abs().gt(2)
        else: feats[name] = pd.Series(False, index=df.index)

    # Distribution-derived volume bands.
    vp = df["volume_pct"].dropna()
    if len(vp):
        q90, q95 = vp.quantile([.90,.95])
        feats["VOL_P90"] = df["volume_pct"].abs().ge(abs(q90))
        feats["VOL_P95"] = df["volume_pct"].abs().ge(abs(q95))

    # Explicit futures state + direction footprint.
    feats["FUT_LB_UP"] = df["fut_dir"].eq("UP") & df["fut_state"].eq("LB")
    feats["FUT_SB_SC_DOWN"] = df["fut_dir"].eq("DOWN") & df["fut_state"].isin(["SB","SC"])

    # Sign-specific variants are retained because sign meaning must be discovered,
    # not assumed to be bullish/bearish for options.
    for base_name, col in [("CE","ce_num"),("PE","pe_num"),("PECE","pec_num"),("FUT_OI","fut_num")]:
        for sign, opx in [("POS", lambda s:s.gt(500)),("NEG",lambda s:s.lt(-500)),
                          ("POS1000",lambda s:s.gt(1000)),("NEG1000",lambda s:s.lt(-1000))]:
            feats[f"{base_name}_{sign}"] = opx(df[col])

    # Diagnostic: report exactly where individual footprint anchors disappear.
    diag_rows = []
    diag_features = ["CE_NUM_GT500","CE_NUM_GT1000","PE_NUM_GT500","PE_NUM_GT1000","PECE_NUM_GT500","PECE_NUM_GT1000",
                     "CE_PCT_GT1","CE_PCT_GT2","PE_PCT_GT1","PE_PCT_GT2","PECE_PCT_GT1","PECE_PCT_GT2",
                     "FUT_OI_GT500","FUT_OI_GT1000","FUT_PCT_GT1","FUT_PCT_GT2","VOL_P90","VOL_P95",
                     "FUT_LB_UP","FUT_SB_SC_DOWN"]
    for name in diag_features:
        m = feats[name].fillna(False).astype(bool)
        ix = np.flatnonzero(m.to_numpy())
        a = df.iloc[ix]
        later = np.zeros(len(ix), dtype=bool)
        if len(ix):
            # A later timestamp is guaranteed by the clean timeline's sequence position.
            later = np.array([bool(j + 1 < len(df)) for j in ix])
        diag_rows.append({
            "footprint": name,
            "anchor_rows": int(len(ix)),
            "anchor_symbols": int(a["symbol"].nunique()) if len(a) else 0,
            "anchor_dates": int(a["trade_date"].nunique()) if len(a) else 0,
            "stock_dir_valid": int(a["stock_dir"].isin(["UP","DOWN"]).sum()) if len(a) else 0,
            "close_valid": int(a["close"].notna().sum()) if len(a) else 0,
            "t1_move_valid": int(a["move_t1_pct"].notna().sum()) if len(a) else 0,
            "t2_move_valid": int(a["move_t2_pct"].notna().sum()) if len(a) else 0,
            "t3_move_valid": int(a["move_t3_pct"].notna().sum()) if len(a) else 0,
            "t5_move_valid": int(a["move_t5_pct"].notna().sum()) if len(a) else 0,
            "t10_move_valid": int(a["move_t10_pct"].notna().sum()) if len(a) else 0,
            "t20_move_valid": int(a["move_t20_pct"].notna().sum()) if len(a) else 0,
            "pricechg_t1_valid": int(a["pricechg_t1"].notna().sum()) if len(a) else 0,
        })
    pd.DataFrame(diag_rows).to_csv(out/"individual_footprint_diagnostic.csv", index=False)
    print("INDIVIDUAL_DIAGNOSTIC_WRITTEN")
    for r in diag_rows:
        print(f"{r['footprint']}: anchors={r['anchor_rows']} dir={r['stock_dir_valid']} t1={r['t1_move_valid']} t2={r['t2_move_valid']} t5={r['t5_move_valid']}")

    # Evaluate each footprint efficiently.
    rows = []
    for name, mask in feats.items():
        idx = np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool))
        if len(idx) < MIN_OUTCOMES:
            continue
        a = df.iloc[idx]
        for h in HORIZONS:
            move = a[f"move_t{h}_pct"]
            # Fallback to the next observation's price-change direction only when
            # anchor-relative close movement is unavailable.
            fallback = a[f"pricechg_t{h}"]
            valid = (a["stock_dir"].isin(["UP","DOWN"]) & (move.notna() | fallback.notna())).fillna(False)
            if not valid.any():
                continue
            av = a.loc[valid]
            mv = move.loc[valid]
            fb = fallback.loc[valid]
            favorable = np.where(
                mv.notna(),
                np.where(av["stock_dir"].to_numpy()=="UP", mv.to_numpy()>0, mv.to_numpy()<0),
                np.where(av["stock_dir"].to_numpy()=="UP", fb.to_numpy()>0, fb.to_numpy()<0)
            ).astype(bool)
            n = int(favorable.size)
            rate = float(favorable.mean()) if n else np.nan
            rows.append({
                "stage":"INDIVIDUAL","footprint":name,"horizon":f"T+{h}",
                "valid_outcomes":n,"favorable":int(favorable.sum()),
                "favorable_rate":rate,
                "dates":int(av["trade_date"].nunique()),
                "symbols":int(av["symbol"].nunique())
            })
    individual = pd.DataFrame(rows)
    if individual.empty:
        raise SystemExit("NO_INDIVIDUAL_FOOTPRINT_OUTCOMES")

    individual.to_csv(out/"individual_footprint_results.csv", index=False)

    # Candidate selection is deliberately statistical/descriptive, not a hard trading threshold.
    cand = individual[
        (individual.valid_outcomes >= MIN_OUTCOMES) &
        (individual.dates >= MIN_DATES) &
        (individual.symbols >= MIN_SYMBOLS)
    ].copy()
    cand = cand.sort_values(["favorable_rate","valid_outcomes"], ascending=[False,False])
    cand.to_csv(out/"recurring_footprint_candidates.csv", index=False)

    # Combination mining only from a small top set per horizon.
    top_names = []
    for h, sub in cand.groupby("horizon"):
        top_names.extend(sub.head(12)["footprint"].tolist())
    top_names = sorted(set(top_names))
    combo_rows = []
    # map feature masks once
    mask_map = {k:v.fillna(False).to_numpy(dtype=bool) for k,v in feats.items()}
    for r in (2,3):
        for names in itertools.combinations(top_names, r):
            mask = np.ones(len(df), dtype=bool)
            for n in names:
                mask &= mask_map[n]
            idx = np.flatnonzero(mask)
            if len(idx) < MIN_OUTCOMES:
                continue
            a = df.iloc[idx]
            for h in HORIZONS:
                future = a[f"pricechg_t{h}"]
                valid = (future.notna() & a["stock_dir"].isin(["UP","DOWN"])).fillna(False)
                if valid.sum() < MIN_OUTCOMES:
                    continue
                av = a.loc[valid]; fv = future.loc[valid]
                favorable = ((av["stock_dir"].to_numpy()=="UP") & (fv.to_numpy()>0)) | ((av["stock_dir"].to_numpy()=="DOWN") & (fv.to_numpy()<0))
                combo_rows.append({
                    "stage":f"{r}_FACTOR","footprint":" + ".join(names),
                    "horizon":f"T+{h}","valid_outcomes":int(len(favorable)),
                    "favorable":int(favorable.sum()),"favorable_rate":float(favorable.mean()),
                    "dates":int(av["trade_date"].nunique()),"symbols":int(av["symbol"].nunique())
                })
    combos = pd.DataFrame(combo_rows)
    if combos.empty:
        combos = pd.DataFrame(columns=["stage","footprint","horizon","valid_outcomes","favorable","favorable_rate","dates","symbols"])
    combos.to_csv(out/"combination_results.csv", index=False)

    all_results = pd.concat([individual, combos], ignore_index=True)
    accepted = all_results[
        (all_results.favorable_rate >= ACCEPT_RATE) &
        (all_results.valid_outcomes >= MIN_OUTCOMES) &
        (all_results.dates >= MIN_DATES) &
        (all_results.symbols >= MIN_SYMBOLS)
    ].sort_values(["favorable_rate","valid_outcomes"], ascending=[False,False])
    accepted.to_csv(out/"accepted_patterns.csv", index=False)

    summary = {
        "status":"FINAL_LOGIC_RESEARCH_COMPLETE",
        "timeline_rows":int(len(df)),
        "symbols":int(df["symbol"].nunique()),
        "dates":int(df["trade_date"].nunique()),
        "individual_footprints_tested":int(len(individual)),
        "recurring_candidates":int(len(cand)),
        "combinations_tested":int(len(combos)),
        "accepted_patterns":int(len(accepted)),
        "acceptance_rule":">=80% favorable rate AND >=30 valid outcomes AND >=3 dates AND >=10 symbols",
        "research_only":True,
        "production_modified":False
    }
    (out/"final_logic_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__ == "__main__":
    main()
