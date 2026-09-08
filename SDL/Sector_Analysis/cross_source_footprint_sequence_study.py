
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import pandas as pd, numpy as np

def norm(x): return re.sub(r"\s+"," ",str(x).lower().replace("_"," ")).strip()
def num(s): return pd.to_numeric(s.astype(str).str.replace(",","",regex=False).str.replace("−","-",regex=False).str.replace("%","",regex=False),errors="coerce")
def exact(cols, aliases):
    mp={norm(c):c for c in cols}
    for a in aliases:
        if norm(a) in mp:return mp[norm(a)]
    return None

def table(p):
    try: xl=pd.ExcelFile(p)
    except:return []
    out=[]
    for sh in xl.sheet_names:
        try: df=pd.read_excel(p,sheet_name=sh)
        except:continue
        sym=exact(df.columns,["Symbol"])
        if not sym:continue
        nm=p.name.lower(); fut="futuresoi" in nm
        m={
          "ce":exact(df.columns,["Tol CE OI Chg","Tot CE OI Chg"]),
          "pe":exact(df.columns,["Tol PE OI Chg","Tot PE OI Chg"]),
          "pec":exact(df.columns,["Tol PE-CE OI Chg","Tot PE-CE OI Chg"]),
          "ce_pct":exact(df.columns,["Tol CE OI Chg %","Tot CE OI Chg %"]),
          "pe_pct":exact(df.columns,["Tol PE OI Chg %","Tot PE OI Chg %"]),
          "pec_pct":exact(df.columns,["Tol PE-CE OI Chg %","Tot PE-CE OI Chg %"]),
          "fut":exact(df.columns,["OI Chg"]) if fut else None,
          "fut_pct":exact(df.columns,["OI Chg %"]) if fut else None,
          "state":exact(df.columns,["Fut Buildup","Buildup"]),
          "price":exact(df.columns,["Price Chg","Price Chg%","Price chg (%)"]),
          "volume":exact(df.columns,["Volume Chg (%)","Volume chg (%)"])
        }
        z=pd.DataFrame({"symbol":df[sym].astype(str).str.strip()})
        for k,c in m.items(): z[k]=df[c] if c is not None else np.nan
        for k in ["ce","pe","pec","ce_pct","pe_pct","pec_pct","fut","fut_pct","price","volume"]:z[k]=num(z[k])
        z["state"]=z.state.astype(str).str.upper().str.extract(r"\b(LB|SB|SC|LO)\b",expand=False)
        z["family"]="FUTURES" if fut else ("OPTIONS" if ("daywise_price_and_oi" in nm or "option" in nm) else "VOLUME")
        z["file"]=str(p); z["sheet"]=sh
        try:z["time"]=pd.Timestamp.fromtimestamp(p.stat().st_ctime)
        except:z["time"]=pd.NaT
        # A source row is useful only if it contains actual evidence, not state alone.
        out.append(z)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
    root,out=Path(a.root),Path(a.out);out.mkdir(parents=True,exist_ok=True)
    frames=[]
    for p in root.rglob("*.xlsx"):
        nm=p.name.lower()
        if any(x in nm for x in ["futuresoi","daywise_price_and_oi","volumeandoispikes","option","volume"]):
            frames+=table(p)
    if not frames:
        print(json.dumps({"status":"NO_DATA","production_modified":False},indent=2));return
    o=pd.concat(frames,ignore_index=True)
    o["date"]=o.time.dt.date.astype(str)
    o["has_option"]=o[["ce","pe","pec","ce_pct","pe_pct","pec_pct"]].notna().any(axis=1)
    o["has_futures"]=o[["fut","fut_pct"]].notna().any(axis=1)
    o["has_volume"]=o.volume.notna()
    o["path"]=np.select([o.has_option&o.has_futures,o.has_option, o.has_futures,o.has_volume],
                        ["OPTION_AND_FUTURES","OPTION_ONLY","FUTURES_ONLY","VOLUME_ONLY"],default="PARTIAL")
    # Strong evidence flags.
    o["opt500"]=o[["ce","pe","pec"]].abs().gt(500).any(axis=1)
    o["opt1000"]=o[["ce","pe","pec"]].abs().gt(1000).any(axis=1)
    o["fut500"]=o.fut.abs().gt(500);o["fut1000"]=o.fut.abs().gt(1000)
    o["fut2pct"]=o.fut_pct.abs().gt(2)
    o["vol50"]=o.volume.abs().gt(50);o["vol100"]=o.volume.abs().gt(100)
    o["direction"]=np.select([o.price>0,o.price<0],["UP","DOWN"],default="UNKNOWN")
    # Cross-source timeline: one symbol/day, all families; duplicate same source/time retained only once per family.
    o=o.sort_values(["symbol","date","time","family","file"]).drop_duplicates(["symbol","date","time","family"],keep="first")
    g=o.groupby(["symbol","date"],dropna=False)
    o["next_time"]=g.time.shift(-1);o["next_price"]=g.price.shift(-1);o["next_family"]=g.family.shift(-1);o["next_direction"]=g.direction.shift(-1)
    o["next_move"]=o.next_price-o.price
    # Only strong footprint observations become sequence anchors.
    anchors=o[o.opt500|o.fut500|o.fut2pct|o.vol50].copy()
    anchors["next_same_direction"]=np.where((anchors.price>0)&(anchors.next_move>0),True,np.where((anchors.price<0)&(anchors.next_move<0),True,False))
    anchors.to_csv(out/"cross_source_sequence_anchors.csv",index=False)

    # Simple sequence labels: what evidence was present at anchor and what arrives next for same symbol/day.
    def evidence(r):
        a=[]
        if r.opt500:a.append("OPTION")
        if r.fut500 or r.fut2pct:a.append("FUTURES")
        if r.vol50:a.append("VOLUME")
        return "+".join(a) if a else "NONE"
    anchors["anchor_evidence"]=anchors.apply(evidence,axis=1)
    anchors["sequence"]=anchors["anchor_evidence"]+" -> "+anchors["next_family"].fillna("NONE")
    stats=(anchors.groupby(["anchor_evidence","direction","next_family"],dropna=False)
           .agg(n=("symbol","size"),continued=("next_same_direction","sum"),
                symbols=("symbol","nunique"),dates=("date","nunique")).reset_index())
    stats["rate"]=np.where(stats.n>0,stats.continued/stats.n,np.nan)
    stats.to_csv(out/"sequence_effectiveness.csv",index=False)

    meta={"status":"CROSS_SOURCE_SEQUENCE_STUDY_COMPLETE","production_modified":False,
          "observations":len(o),"anchors":len(anchors),"symbols":int(o.symbol.nunique()),
          "dates":int(o.date.nunique()),"timestamped":int(o.time.notna().sum()),
          "outputs":["cross_source_sequence_anchors.csv","sequence_effectiveness.csv"]}
    (out/"research_summary.json").write_text(json.dumps(meta,indent=2),encoding="utf-8");print(json.dumps(meta,indent=2))
if __name__=="__main__":main()
