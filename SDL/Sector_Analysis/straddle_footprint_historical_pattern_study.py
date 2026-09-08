
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import pandas as pd
import numpy as np

# Offline research only. Production/dashboard untouched.
# Primary evidence: Daywise/option/futures/volume stock tables.
# NUMBER and PERCENT are deliberately independent.

def n(s): return re.sub(r"\s+"," ",str(s).lower().replace("_"," ")).strip()
def pct(c): return "%" in str(c) or "percent" in n(c)

def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",","",regex=False)
                         .str.replace("−","-",regex=False).str.replace("%","",regex=False),
                         errors="coerce")

def exact(cols, aliases):
    mp={n(c):c for c in cols}
    for a in aliases:
        if n(a) in mp:return mp[n(a)]
    return None

def contains(cols, aliases):
    # safe: longest/specific aliases first; never let PE-CE match CE.
    for c in cols:
        nc=n(c)
        for a in sorted(aliases,key=len,reverse=True):
            if nc==n(a): return c
    return None

def read_table(p):
    try:
        xl=pd.ExcelFile(p)
    except:return []
    out=[]
    for sh in xl.sheet_names:
        try: df=pd.read_excel(p,sheet_name=sh)
        except:continue
        if df.empty:continue
        cols=list(df.columns)
        sym=exact(cols,["symbol"])
        if not sym: continue
        # Only recognize exact physical fields.
        m={}
        m["ce_num"]=exact(cols,["Tol CE OI Chg","Tot CE OI Chg"])
        m["pe_num"]=exact(cols,["Tol PE OI Chg","Tot PE OI Chg"])
        m["pec_num"]=exact(cols,["Tol PE-CE OI Chg","Tot PE-CE OI Chg"])
        m["ce_pct"]=exact(cols,["Tol CE OI Chg %","Tot CE OI Chg %"])
        m["pe_pct"]=exact(cols,["Tol PE OI Chg %","Tot PE OI Chg %"])
        m["pec_pct"]=exact(cols,["Tol PE-CE OI Chg %","Tot PE-CE OI Chg %"])
        m["fut_num"]=exact(cols,["OI Chg"])
        m["fut_pct"]=exact(cols,["OI Chg %"])
        m["state"]=exact(cols,["Fut Buildup","Buildup"])
        m["price"]=exact(cols,["Price Chg","Price Chg%","Price chg (%)"])
        m["volume"]=exact(cols,["Volume Chg (%)","Volume chg (%)"])
        if not any(m.values()):continue
        z=pd.DataFrame({"symbol":df[sym].astype(str).str.strip()})
        for k,c in m.items():
            if c is not None:z[k]=df[c]
            else:z[k]=np.nan
        for k in ["ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","price","volume"]:
            z[k]=num(z[k])
        z["state"]=z["state"].astype(str).str.upper().str.extract(r"\b(LB|SB|SC|LO)\b",expand=False)
        z["source_file"]=str(p);z["sheet"]=sh
        try:
            st=p.stat()
            z["file_ctime"]=pd.Timestamp.fromtimestamp(st.st_ctime)
        except:z["file_ctime"]=pd.NaT
        out.append(z)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True);ap.add_argument("--out",required=True)
    args=ap.parse_args()
    root,out=Path(args.root),Path(args.out);out.mkdir(parents=True,exist_ok=True)

    files=list(root.rglob("*.xlsx"))
    frames=[]
    for p in files:
        # Target relevant families only; avoid unrelated Support/Resistance etc.
        name=p.name.lower()
        if not any(x in name for x in ["futuresoi","daywise_price_and_oi","volumeandoispikes","volum","option"]):
            continue
        frames.extend(read_table(p))
    if not frames:
        print(json.dumps({"status":"NO_MATCHING_DATA","production_modified":False},indent=2));return
    obs=pd.concat(frames,ignore_index=True)
    obs["date"]=obs["file_ctime"].dt.date.astype(str)
    obs=obs.sort_values(["symbol","file_ctime","source_file"]).drop_duplicates(
        ["symbol","file_ctime","source_file"],keep="last")
    obs.to_csv(out/"historical_footprint_observations.csv",index=False)

    # Evidence flags; missing is never treated as zero.
    obs["opt_large"]=((obs[["ce_num","pe_num","pec_num"]].abs()>500).any(axis=1))
    obs["opt_remarkable"]=((obs[["ce_num","pe_num","pec_num"]].abs()>1000).any(axis=1))
    obs["fut_large_num"]=obs["fut_num"].abs()>500
    obs["fut_remarkable_num"]=obs["fut_num"].abs()>1000
    obs["fut_large_pct"]=obs["fut_pct"].abs()>1
    obs["fut_remarkable_pct"]=obs["fut_pct"].abs()>2
    obs["volume_large"]=obs["volume"].abs()>50
    obs["volume_remarkable"]=obs["volume"].abs()>100

    def path(r):
        o=pd.notna(r["ce_num"]) or pd.notna(r["pe_num"]) or pd.notna(r["pec_num"])
        f=pd.notna(r["fut_num"]) or pd.notna(r["fut_pct"]) or pd.notna(r["state"])
        v=pd.notna(r["volume"])
        if o and f:return "OPTION_AND_FUTURES"
        if o:return "OPTION_ONLY"
        if f:return "FUTURES_ONLY"
        if v:return "VOLUME_ONLY"
        return "PRICE_ONLY_OR_PARTIAL"
    obs["evidence_path"]=obs.apply(path,axis=1)

    # Direction from price change where available; otherwise unavailable.
    obs["price_direction"]=np.select([obs["price"]>0,obs["price"]<0],["UP","DOWN"],default="FLAT_OR_UNKNOWN")

    # Compact path summary.
    rows=[]
    for p,g in obs.groupby("evidence_path",dropna=False):
        rows.append({
            "evidence_path":p,"observations":len(g),"symbols":g.symbol.nunique(),
            "dates":g.date.nunique(),"timestamped":g.file_ctime.notna().sum(),
            "option_large":int(g.opt_large.sum()),"option_remarkable":int(g.opt_remarkable.sum()),
            "futures_large_number":int(g.fut_large_num.sum()),
            "futures_remarkable_number":int(g.fut_remarkable_num.sum()),
            "futures_large_percent":int(g.fut_large_pct.sum()),
            "futures_remarkable_percent":int(g.fut_remarkable_pct.sum()),
            "volume_large":int(g.volume_large.sum()),
            "volume_remarkable":int(g.volume_remarkable.sum())
        })
    pd.DataFrame(rows).to_csv(out/"evidence_path_summary.csv",index=False)

    # Candidate footprint sequences: only events where a strong footprint exists,
    # compared with the next chronological observation for the same symbol.
    obs=obs.reset_index(drop=True)
    obs["next_price"]=obs.groupby("symbol")["price"].shift(-1)
    obs["next_time"]=obs.groupby("symbol")["file_ctime"].shift(-1)
    obs["next_move"]=obs["next_price"]-obs["price"]
    cand=obs[(obs.opt_large|obs.opt_remarkable|obs.fut_large_num|obs.fut_large_pct|obs.volume_large)].copy()
    cand["continuation_same_direction"]=np.where(
        (cand.price>0)&(cand.next_move>0),True,
        np.where((cand.price<0)&(cand.next_move<0),True,False))
    cand[["symbol","date","file_ctime","evidence_path","price","price_direction",
          "ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct",
          "fut_num","fut_pct","state","volume","next_time","next_move",
          "continuation_same_direction"]].to_csv(out/"chronological_footprint_candidates.csv",index=False)

    summary={
        "status":"HISTORICAL_PATTERN_STUDY_COMPLETE",
        "production_modified":False,
        "files_scanned":len(files),
        "observations":len(obs),
        "symbols":int(obs.symbol.nunique()),
        "dates":int(obs.date.nunique()),
        "timestamped":int(obs.file_ctime.notna().sum()),
        "option_remarkable":int(obs.opt_remarkable.sum()),
        "futures_remarkable_number":int(obs.fut_remarkable_num.sum()),
        "futures_remarkable_percent":int(obs.fut_remarkable_pct.sum()),
        "volume_remarkable":int(obs.volume_remarkable.sum()),
        "outputs":["historical_footprint_observations.csv","evidence_path_summary.csv","chronological_footprint_candidates.csv"]
    }
    (out/"research_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
