from pathlib import Path
import argparse,json,re
import pandas as pd, numpy as np

def norm(x): return re.sub(r"\s+"," ",str(x).lower().replace("_"," ")).strip()
def num(s): return pd.to_numeric(s.astype(str).str.replace(",","",regex=False).str.replace("−","-",regex=False).str.replace("%","",regex=False),errors="coerce")
def exact(cols, aliases):
    mp={norm(c):c for c in cols}
    for a in aliases:
        if norm(a) in mp:return mp[norm(a)]
    return None

def read(p):
    try: xl=pd.ExcelFile(p)
    except:return []
    out=[]
    for sh in xl.sheet_names:
        try: df=pd.read_excel(p,sheet_name=sh)
        except:continue
        if df.empty:continue
        cols=list(df.columns); sym=exact(cols,["Symbol"])
        if not sym:continue
        fut="futuresoi" in p.name.lower()
        m={
          "ce_num":exact(cols,["Tol CE OI Chg","Tot CE OI Chg"]),
          "pe_num":exact(cols,["Tol PE OI Chg","Tot PE OI Chg"]),
          "pec_num":exact(cols,["Tol PE-CE OI Chg","Tot PE-CE OI Chg"]),
          "ce_pct":exact(cols,["Tol CE OI Chg %","Tot CE OI Chg %"]),
          "pe_pct":exact(cols,["Tol PE OI Chg %","Tot PE OI Chg %"]),
          "pec_pct":exact(cols,["Tol PE-CE OI Chg %","Tot PE-CE OI Chg %"]),
          "fut_num":exact(cols,["OI Chg"]) if fut else None,
          "fut_pct":exact(cols,["OI Chg %"]) if fut else None,
          "state":exact(cols,["Fut Buildup","Buildup"]),
          "price":exact(cols,["Price Chg","Price Chg%","Price chg (%)"]),
          "volume":exact(cols,["Volume Chg (%)","Volume chg (%)"])
        }
        if not any(m.values()):continue
        z=pd.DataFrame({"symbol":df[sym].astype(str).str.strip()})
        for k,c in m.items(): z[k]=df[c] if c is not None else np.nan
        for k in ["ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","price","volume"]: z[k]=num(z[k])
        z["state"]=z["state"].astype(str).str.upper().str.extract(r"\b(LB|SB|SC|LO)\b",expand=False)
        z["source_file"]=str(p); z["sheet"]=sh
        try:z["file_ctime"]=pd.Timestamp.fromtimestamp(p.stat().st_ctime)
        except:z["file_ctime"]=pd.NaT
        z["family"]="FUTURES" if fut else ("OPTIONS" if "daywise_price_and_oi" in p.name.lower() or "option" in p.name.lower() else "VOLUME")
        out.append(z)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    root,out=Path(a.root),Path(a.out); out.mkdir(parents=True,exist_ok=True)
    frames=[]
    for p in root.rglob("*.xlsx"):
        nm=p.name.lower()
        if any(x in nm for x in ["futuresoi","daywise_price_and_oi","volumeandoispikes","option","volume"]): frames.extend(read(p))
    if not frames: print(json.dumps({"status":"NO_DATA","production_modified":False},indent=2)); return
    o=pd.concat(frames,ignore_index=True); o["date"]=o.file_ctime.dt.date.astype(str)
    o["has_option"]=o[["ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct"]].notna().any(axis=1)
    o["has_futures_oi"]=o[["fut_num","fut_pct"]].notna().any(axis=1)
    o["has_volume"]=o.volume.notna()
    o["evidence_path"]=np.select([o.has_option&o.has_futures_oi,o.has_option&~o.has_futures_oi,~o.has_option&o.has_futures_oi,~o.has_option&~o.has_futures_oi&o.has_volume],["OPTION_AND_FUTURES","OPTION_ONLY","FUTURES_ONLY","VOLUME_ONLY"],default="PRICE_ONLY_OR_PARTIAL")
    o["price_direction"]=np.select([o.price>0,o.price<0],["UP","DOWN"],default="FLAT_OR_UNKNOWN")
    o["option_large"]=o[["ce_num","pe_num","pec_num"]].abs().gt(500).any(axis=1); o["option_remarkable"]=o[["ce_num","pe_num","pec_num"]].abs().gt(1000).any(axis=1)
    o["fut_large_num"]=o.fut_num.abs().gt(500); o["fut_remarkable_num"]=o.fut_num.abs().gt(1000); o["fut_large_pct"]=o.fut_pct.abs().gt(1); o["fut_remarkable_pct"]=o.fut_pct.abs().gt(2)
    o["volume_large"]=o.volume.abs().gt(50); o["volume_remarkable"]=o.volume.abs().gt(100)
    o=o.sort_values(["symbol","file_ctime","source_file","family"]).reset_index(drop=True)
    o.to_csv(out/"historical_footprint_observations.csv",index=False)
    summ=(o.groupby("evidence_path").agg(observations=("symbol","size"),symbols=("symbol","nunique"),dates=("date","nunique"),timestamped=("file_ctime","count"),option_large=("option_large","sum"),option_remarkable=("option_remarkable","sum"),futures_large_number=("fut_large_num","sum"),futures_remarkable_number=("fut_remarkable_num","sum"),futures_large_percent=("fut_large_pct","sum"),futures_remarkable_percent=("fut_remarkable_pct","sum"),volume_large=("volume_large","sum"),volume_remarkable=("volume_remarkable","sum")).reset_index())
    summ.to_csv(out/"evidence_path_summary.csv",index=False)
    g=o.groupby(["symbol","family"],dropna=False); o["next_price"]=g.price.shift(-1); o["next_time"]=g.file_ctime.shift(-1); o["next_move"]=o.next_price-o.price
    cand=o[(o.option_large|o.fut_large_num|o.fut_large_pct|o.volume_large)].copy(); cand["continuation_same_direction"]=np.where((cand.price>0)&(cand.next_move>0),True,np.where((cand.price<0)&(cand.next_move<0),True,False))
    cand[["symbol","date","file_ctime","family","evidence_path","price","price_direction","ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","state","volume","next_time","next_move","continuation_same_direction"]].to_csv(out/"chronological_footprint_candidates.csv",index=False)
    meta={"status":"HISTORICAL_PATTERN_STUDY_V2_COMPLETE","production_modified":False,"files_scanned":len(list(root.rglob("*.xlsx"))),"observations":len(o),"symbols":int(o.symbol.nunique()),"dates":int(o.date.nunique()),"timestamped":int(o.file_ctime.notna().sum()),"option_remarkable":int(o.option_remarkable.sum()),"futures_remarkable_number":int(o.fut_remarkable_num.sum()),"futures_remarkable_percent":int(o.fut_remarkable_pct.sum()),"volume_remarkable":int(o.volume_remarkable.sum())}
    (out/"research_summary.json").write_text(json.dumps(meta,indent=2),encoding="utf-8"); print(json.dumps(meta,indent=2))
if __name__=="__main__": main()
