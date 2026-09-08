import argparse, json
from pathlib import Path
import pandas as pd

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    base=out.parent.parent
    hits=list(base.rglob("canonical_strength_observations.csv"))
    if not hits: raise SystemExit("CACHE_NOT_FOUND")
    p=max(hits,key=lambda x:x.stat().st_mtime)
    print(f"CACHE_FOUND: {p}")
    df=pd.read_csv(p,nrows=5,low_memory=False)
    cols=list(df.columns)
    print(f"COLUMNS: {len(cols)}")
    for i,c in enumerate(cols,1):
        print(f"{i:03d}: {c}")

    groups={
      "options_number":["ce_num","pe_num","pece_num","tol_ce_oi_chg","tot_ce_oi_chg","tol_pe_oi_chg","tot_pe_oi_chg","tol_pe_ce_oi_chg","tot_pe_ce_oi_chg"],
      "options_percent":["ce_pct","pe_pct","pece_pct","tol_ce_oi_chg_pct","tot_ce_oi_chg_pct","tol_pe_oi_chg_pct","tot_pe_oi_chg_pct","tol_pe_ce_oi_chg_pct","tot_pe_ce_oi_chg_pct"],
      "futures_number":["fut_oi_num","oi_chg"],
      "futures_percent":["fut_oi_pct","oi_chg_pct"],
      "futures_state":["fut_state","fut_buildup","buildup"],
      "futures_price":["fut_price_chg","futures_price_chg"],
      "volume":["volume_pct","volume_chg_pct","volume_chg"],
      "price":["price_chg","price_chg_pct"],
      "ohlc":["open","high","low","close"],
      "identity":["symbol","trade_date","timestamp"]
    }
    norm={c.lower().strip().replace(" ","_"):c for c in cols}
    found={}
    for g,names in groups.items():
        found[g]=[]
        for n in names:
            if n in norm: found[g].append(norm[n])
    result={"status":"CANONICAL_SCHEMA_MAPPING_AUDIT_COMPLETE","cache":str(p),"column_count":len(cols),"groups":found}
    (out/"schema_mapping_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
