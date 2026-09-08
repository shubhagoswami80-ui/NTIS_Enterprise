
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import pandas as pd

# Targeted offline study only. No dashboard/production files are modified.
# Native units are kept separate: NUMBER vs PERCENT.

OPTION_NUM = {
    "ce": ["ce oi change", "tol ce oi chg", "ce_oi_chg", "ce oi chg"],
    "pe": ["pe oi change", "tol pe oi chg", "pe_oi_chg", "pe oi chg"],
    "pe_ce": ["pe-ce oi change", "tol pe-ce oi chg", "pe_ce_oi_chg", "pe-ce oi chg"],
}
OPTION_PCT = {
    "ce": ["ce oi change %", "tol ce oi chg %", "ce_oi_chg_pct", "ce oi chg %"],
    "pe": ["pe oi change %", "tol pe oi chg %", "pe_oi_chg_pct", "pe oi chg %"],
    "pe_ce": ["pe-ce oi change %", "tol pe-ce oi chg %", "pe_ce_oi_chg_pct", "pe-ce oi chg %"],
}
FUT_NUM = ["futures oi change", "future oi change", "futures_oI_change", "futures oi chg", "future oi chg"]
FUT_PCT = ["futures oi change %", "future oi change %", "futures_oi_change_pct", "futures oi chg %", "future oi chg %"]
FUT_STATE = ["futures state", "future state", "buildup", "futures buildup", "future buildup"]
PRICE = ["price chg (%)", "price change %", "price chg", "price change", "price_chg_pct"]
VOLUME_NUM = ["volume change", "volume chg", "volume_chg", "volume change number"]
VOLUME_PCT = ["volume change %", "volume chg (%)", "volume_chg_pct", "volume chg %"]
SYMBOL = ["symbol", "stock", "scrip", "security"]
TIME = ["timestamp", "observation timestamp", "datetime", "date time", "time"]

def norm(s): return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()
def find_col(cols, aliases):
    m={norm(c):c for c in cols}
    for a in aliases:
        if norm(a) in m: return m[norm(a)]
    # conservative contains match
    for c in cols:
        nc=norm(c)
        for a in aliases:
            na=norm(a)
            if na and na in nc: return c
    return None

def num(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("−", "-", regex=False)
         .str.strip(), errors="coerce"
    )

def classify_state(x):
    s=str(x).upper().strip()
    for k in ("LB","SB","SC","LO"):
        if re.search(rf"\b{k}\b", s): return k
    return ""

def threshold_rows(df, source, field, unit, vals):
    if field is None: return []
    x=num(df[field])
    out=[]
    for label, mask in [
        ("LT_-1000", x < -1000), ("LT_-500", x < -500),
        ("GT_500", x > 500), ("GT_1000", x > 1000),
    ]:
        if unit=="PERCENT" and source=="futures":
            # Number-style extremes are still tested separately only when this is
            # genuinely a numeric futures-number field.
            pass
        n=int(mask.sum())
        if n:
            out.append({"source":source,"field":field,"unit":unit,"condition":label,
                        "count":n,"min":float(x[mask].min()),"max":float(x[mask].max())})
    return out

def inspect_file(path):
    try:
        xl=pd.ExcelFile(path)
        sheets=xl.sheet_names
    except Exception:
        return None
    all_diag=[]; frames=[]
    for sh in sheets:
        try: df=pd.read_excel(path,sheet_name=sh)
        except Exception: continue
        if df.empty: continue
        # Only retain tables that have a symbol or relevant evidence field.
        sym=find_col(df.columns,SYMBOL)
        relevant=any(find_col(df.columns,a) for a in list(OPTION_NUM.values())+list(OPTION_PCT.values())+[FUT_NUM,FUT_PCT,FUT_STATE,VOLUME_NUM,VOLUME_PCT])
        if not (sym or relevant): continue
        mapping={}
        for k,a in OPTION_NUM.items(): mapping[f"option_{k}_number"]=find_col(df.columns,a)
        for k,a in OPTION_PCT.items(): mapping[f"option_{k}_percent"]=find_col(df.columns,a)
        mapping["futures_oi_number"]=find_col(df.columns,FUT_NUM)
        mapping["futures_oi_percent"]=find_col(df.columns,FUT_PCT)
        mapping["futures_state"]=find_col(df.columns,FUT_STATE)
        mapping["price"]=find_col(df.columns,PRICE)
        mapping["volume_number"]=find_col(df.columns,VOLUME_NUM)
        mapping["volume_percent"]=find_col(df.columns,VOLUME_PCT)
        mapping["symbol"]=sym
        mapping["timestamp"]=find_col(df.columns,TIME)
        for key,col in mapping.items():
            if col is None: continue
            x=num(df[col]) if key!="futures_state" else pd.Series(dtype=float)
            d={"file":str(path),"sheet":sh,"field_role":key,"column":str(col),
               "rows":len(df),"numeric_valid":int(x.notna().sum()) if len(x) else None,
               "numeric_rate":float(x.notna().mean()) if len(x) else None}
            if len(x):
                d.update(min=float(x.min()),max=float(x.max()),
                         gt500=int((x>500).sum()),lt500=int((x<-500).sum()),
                         gt1000=int((x>1000).sum()),lt1000=int((x<-1000).sum()),
                         sample=" | ".join(map(str,x.dropna().head(8).tolist())))
            else:
                d["sample"]=" | ".join(map(str,df[col].dropna().head(8).tolist()))
            all_diag.append(d)
        # Make compact evidence frame for event-pattern discovery.
        present=[c for c in mapping.values() if c is not None]
        if mapping["symbol"] and len(present)>=2:
            keep={role:col for role,col in mapping.items() if col is not None}
            z=pd.DataFrame()
            for role,col in keep.items():
                z[role]=df[col]
            z["source_file"]=str(path); z["source_sheet"]=sh
            if mapping["timestamp"]: z["timestamp"]=pd.to_datetime(z["timestamp"],errors="coerce",format="mixed")
            if mapping["futures_state"]: z["futures_state"]=z["futures_state"].map(classify_state)
            for c in z.columns:
                if c not in ("symbol","timestamp","source_file","source_sheet","futures_state"):
                    z[c]=num(z[c])
            frames.append(z)
    return all_diag,frames

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,help="Permanent raw screenshot repository")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    root=Path(args.root); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    files=[p for p in root.rglob("*.xlsx") if "Sector_Summary" not in p.name]  # stock/evidence reports; sector summary is separate
    diagnostics=[]; frames=[]
    for i,p in enumerate(files,1):
        r=inspect_file(p)
        if r:
            d,f=r; diagnostics.extend(d); frames.extend(f)
    if diagnostics:
        dd=pd.DataFrame(diagnostics)
        dd.to_csv(out/"field_value_audit.csv",index=False)
    if frames:
        obs=pd.concat(frames,ignore_index=True)
        # Deduplicate exact source rows, keep missing as missing.
        obs.to_csv(out/"targeted_observations.csv",index=False)
        # Threshold summary across native fields.
        summaries=[]
        for c in obs.columns:
            if c in ("source_file","source_sheet","symbol","timestamp","futures_state"): continue
            unit="PERCENT" if "percent" in c else "NUMBER"
            source="options" if c.startswith("option_") else "futures" if c.startswith("futures_") else "volume" if c.startswith("volume_") else "price"
            x=num(obs[c])
            for lab,mask in [("LT_-1000",x<-1000),("LT_-500",x<-500),("GT_500",x>500),("GT_1000",x>1000)]:
                summaries.append({"field":c,"source":source,"unit":unit,"condition":lab,
                                  "count":int(mask.sum()),"symbols":int(obs.loc[mask,"symbol"].nunique()) if "symbol" in obs else 0})
            if source=="futures" and unit=="PERCENT":
                for lab,mask in [("GT_1pct",x>1),("GT_2pct",x>2),("LT_-1pct",x<-1),("LT_-2pct",x<-2)]:
                    summaries.append({"field":c,"source":source,"unit":unit,"condition":lab,
                                      "count":int(mask.sum()),"symbols":int(obs.loc[mask,"symbol"].nunique()) if "symbol" in obs else 0})
        pd.DataFrame(summaries).to_csv(out/"threshold_summary.csv",index=False)
    meta={"status":"TARGETED_STUDY_COMPLETE","production_modified":False,
          "xlsx_scanned":len(files),"diagnostic_rows":len(diagnostics),
          "observation_rows":sum(len(x) for x in frames),
          "outputs":[p.name for p in out.iterdir()]}
    (out/"research_summary.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta,indent=2))

if __name__=="__main__": main()
