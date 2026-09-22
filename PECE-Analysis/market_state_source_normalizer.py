from pathlib import Path
import re
import pandas as pd

PATTERNS = {
 "daywise":"Daywise_Price_and_OI_Summary_*.xlsx",
 "ivr_ivp":"IVR-IVP_*_Report_*.xlsx",
 "resistance":"Resistance_*_Scan_*.xlsx",
 "sector":"Sector_Summary_*_Report_*.xlsx",
 "support_resistance":"Support_Resistance_*_Scan_*.xlsx",
 "spikes":"VolumeAndOISpikesScans_*_Report_*.xlsx"
}

def snapshot_time(path):
    m=re.search(r"(20\d{6})_(\d{6})",Path(path).name)
    return pd.to_datetime(m.group(1)+m.group(2),format="%Y%m%d%H%M%S") if m else pd.NaT

def clean(df):
    df=df.copy()
    df.columns=[str(c).strip() for c in df.columns]
    return df

def discover_cycles(source_root):
    root=Path(source_root)
    days=sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"20\d\d-\d\d-\d\d",p.name))
    cycles=[]
    for day in days:
        files={}
        for typ,pattern in PATTERNS.items():
            candidates=sorted(day.glob(pattern))
            for p in candidates:
                files.setdefault(snapshot_time(p),{})[typ]=p
        for ts,group in sorted(files.items()):
            missing=[x for x in PATTERNS if x not in group]
            if not missing:
                cycles.append({"date":day.name,"snapshot_time":ts,**{k:v for k,v in group.items()}})
    return cycles

def canonical_cycle(cycle):
    # Daywise is the canonical stock-level table. Other reports are attached
    # explicitly with report prefixes, preventing pandas _x/_y collisions.
    base=clean(pd.read_excel(cycle["daywise"]))
    if "Symbol" not in base.columns:
        raise ValueError("Daywise report has no Symbol column")
    base["Symbol"]=base["Symbol"].astype(str).str.strip()
    base=base[base["Symbol"].ne("")].drop_duplicates("Symbol").copy()
    base["snapshot_time"]=cycle["snapshot_time"]
    base["source_date"]=cycle["date"]

    specs={
      "ivr_ivp":["PCR","IV","IV Chg (%)","IVR","IVP","IV/HV10 %","IV/HV20 %","IV/HV30 %","IV Range (1Yr)","HV (10/20/30 Days)"],
      "resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],
      "sector":["Sector Name","Price chg (%)","Volume chg (%)","OI chg (%)","Buildup","Tol CE OI Chg","Tol PE OI Chg","Tol PE-CE OI Chg","Tol PE-CE OI Chg %"],
      "support_resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],
      "spikes":["OI chg (%)","OI Chg (Value)","Volume Chg (%)"]
    }
    for typ,cols in specs.items():
        t=clean(pd.read_excel(cycle[typ]))
        if typ=="ivr_ivp" and len(t) and str(t.iloc[0,0]).strip()=="Symbol":
            t=t.iloc[1:].copy()
        if "Symbol" not in t.columns: continue
        t["Symbol"]=t["Symbol"].astype(str).str.strip()
        keep=[c for c in cols if c in t.columns]
        if not keep: continue
        # Explicit source prefix; no collision with canonical Daywise fields.
        t=t[["Symbol"]+keep].drop_duplicates("Symbol")
        t=t.rename(columns={c:f"{typ}__{c}" for c in keep})
        base=base.merge(t,on="Symbol",how="left",validate="one_to_one")
    return base
