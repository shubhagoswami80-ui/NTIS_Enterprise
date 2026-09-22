from pathlib import Path
import re
import numpy as np
import pandas as pd

PATTERNS = {
 "daywise":"Daywise_Price_and_OI_Summary_*.xlsx",
 "ivr_ivp":"IVR-IVP_*_Report_*.xlsx",
 "resistance":"Resistance_*_Scan_*.xlsx",
 "sector":"Sector_Summary_*_Report_*.xlsx",
 "support_resistance":"Support_Resistance_*_Scan_*.xlsx",
 "spikes":"VolumeAndOISpikesScans_*_Report_*.xlsx"
}

LINEAGE = {
 "price":["daywise.Price","ivr_ivp.Price","resistance.Price","support_resistance.Price","spikes.Price"],
 "price_change_pct":["daywise.Price Chg %","ivr_ivp.Price Chg (%)","resistance.Price Chg%","support_resistance.Price Chg%","spikes.Price chg (%)"],
 "futures_oi_change_pct":["daywise.OI Chg %","resistance.Fut OI Chg %","support_resistance.Fut OI Chg %"],
 "futures_buildup":["daywise.Buildup","resistance.Fut Buildup","support_resistance.Fut Buildup"],
 "volume_change_pct":["daywise.Volume Chg (%)","spikes.Volume Chg (%)"],
 "pcr":["ivr_ivp.PCR"], "pcr_change_pct":["daywise.PCR Chg %"],
 "iv":["daywise.IV","ivr_ivp.IV"], "iv_change_pct":["daywise.IV Chg %","ivr_ivp.IV Chg (%)"],
 "ivr":["daywise.IVR","ivr_ivp.IVR"], "ivp":["daywise.IVP","ivr_ivp.IVP"],
 "mwpl_pct":["daywise.MWPL (%)"], "mwpl_change_pct":["daywise.MWPL (%) Chg"],
 "ce_oi":["daywise.Tot CE OI"], "pe_oi":["daywise.Tot PE OI"],
 "pe_minus_ce_oi":["daywise.Tot PE-CE OI"], "pe_minus_ce_oi_change":["daywise.Tot PE-CE OI Chg"],
 "ce_oi_change_pct":["daywise.Tot CE OI Chg %"], "pe_oi_change_pct":["daywise.Tot PE OI Chg %"],
 "rollover_pct":["daywise.Rollover (%)"], "delivery_pct":["daywise.Delivery (%)"],
 "vwap":["daywise.VWAP"], "max_pain":["daywise.Max Pain"],
 "sector_price_change_pct":["sector.Price chg (%)"], "sector_volume_change_pct":["sector.Volume chg (%)"],
 "sector_oi_change_pct":["sector.OI chg (%)"]
}

def num(s):
    if pd.isna(s): return np.nan
    try: return float(str(s).replace(",","").replace("%","").strip())
    except: return np.nan

def snap(path):
    m=re.search(r"(20\d{6})_(\d{6})",path.name)
    return pd.to_datetime(m.group(1)+m.group(2),format="%Y%m%d%H%M%S") if m else pd.NaT

def read(path):
    d=pd.read_excel(path); d.columns=[str(c).strip() for c in d.columns]; return d

def build(source_root, day_filter=None):
    root=Path(source_root)
    days=[root/day_filter] if day_filter else sorted(
        [p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"20\d\d-\d\d-\d\d",p.name)]
    )
    all_rows=[]; inputs=[]

    def files_for(day,key):
        return sorted(day.glob(PATTERNS[key]), key=lambda p: (snap(p) if pd.notna(snap(p)) else pd.Timestamp.max, p.name))

    for day in days:
        anchors=files_for(day,"daywise")
        if not anchors:
            continue

        # Each Daywise workbook is a genuine snapshot anchor. Other reports are
        # paired by nearest filename timestamp within the same capture cycle.
        report_lists={k:files_for(day,k) for k in PATTERNS}
        for anchor in anchors:
            anchor_ts=snap(anchor)
            paths={"daywise":anchor}
            for k in PATTERNS:
                if k=="daywise": continue
                candidates=report_lists[k]
                if not candidates or pd.isna(anchor_ts):
                    paths[k]=None
                    continue
                scored=[]
                for q in candidates:
                    qts=snap(q)
                    if pd.notna(qts):
                        delta=abs((qts-anchor_ts).total_seconds())
                        if delta<=180:
                            scored.append((delta,q))
                paths[k]=min(scored,key=lambda x:x[0])[1] if scored else None

            # Require the six-report cycle to be complete. Incomplete cycles are
            # logged and skipped rather than silently mixing different snapshots.
            if any(paths[k] is None for k in PATTERNS):
                for k,pth in paths.items():
                    inputs.append({
                        "date":day.name,"anchor":anchor.name,"report":k,
                        "file":str(pth) if pth else "",
                        "snapshot_time":snap(pth) if pth else pd.NaT,
                        "rows":0,"status":"MISSING_OR_OUTSIDE_180S_CYCLE"
                    })
                continue

            tabs={}
            cycle_ok=True
            for k,pth in paths.items():
                try:
                    tabs[k]=read(pth)
                    if k=="ivr_ivp" and len(tabs[k]) and str(tabs[k].iloc[0,0]).strip()=="Symbol":
                        tabs[k]=tabs[k].iloc[1:].copy()
                    inputs.append({
                        "date":day.name,"anchor":anchor.name,"report":k,
                        "file":str(pth),"snapshot_time":snap(pth),
                        "rows":len(tabs[k]),"status":"OK"
                    })
                except Exception as e:
                    tabs[k]=pd.DataFrame(); cycle_ok=False
                    inputs.append({
                        "date":day.name,"anchor":anchor.name,"report":k,
                        "file":str(pth),"snapshot_time":snap(pth),
                        "rows":0,"status":f"ERROR: {e}"
                    })
            if not cycle_ok:
                continue

            b=tabs["daywise"].copy()
            if b.empty or "Symbol" not in b.columns:
                continue
            b["Symbol"]=b["Symbol"].astype(str).str.strip()
            b=b[b["Symbol"].ne("")].copy()
            b["snapshot_time"]=anchor_ts
            b["source_date"]=day.name
            b["source_daywise_file"]=anchor.name

            merge_sets={
              "ivr_ivp":["PCR","IV","IV Chg (%)","IVR","IVP","IV/HV10 %","IV/HV20 %","IV/HV30 %","IV Range (1Yr)","HV (10/20/30 Days)"],
              "resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],
              "support_resistance":["Strike","Call OI","Call OI Chg","Put OI","Put OI Chg","Dist. From Strike %","Fut Buildup"],
              "spikes":["OI chg (%)","OI Chg (Value)","Volume Chg (%)"],
              "sector":["Sector Name","Price chg (%)","Volume chg (%)","OI chg (%)","Buildup","Tol CE OI Chg","Tol PE OI Chg","Tol PE-CE OI Chg","Tol PE-CE OI Chg %"]
            }
            for k,cols in merge_sets.items():
                t=tabs[k]
                if t.empty or "Symbol" not in t.columns:
                    continue
                t=t.copy(); t["Symbol"]=t["Symbol"].astype(str).str.strip()
                keep=[c for c in cols if c in t.columns and c not in b.columns]
                if keep:
                    t=t[["Symbol"]+keep].drop_duplicates("Symbol")
                    t=t.rename(columns={c:f"{k}__{c}" for c in keep})
                    b=b.merge(t,on="Symbol",how="left")

            for c in ["Price Chg %","OI Chg %","Volume Chg (%)","PCR Chg %","MWPL (%)","MWPL (%) Chg","IV","IV Chg %","IVR","IVP","Tot CE OI","Tot PE OI","Tot PE-CE OI","Tot PE-CE OI Chg","Tot CE OI Chg %","Tot PE OI Chg %","Rollover (%)","Delivery (%)","VWAP","Max Pain","5D Price Chg %","5D OI Chg %"]:
                if c in b.columns: b[c]=b[c].map(num)

            b["futures_positioning"]=np.select(
              [(b["Price Chg %"]>0)&(b["OI Chg %"]>0),
               (b["Price Chg %"]<0)&(b["OI Chg %"]>0),
               (b["Price Chg %"]>0)&(b["OI Chg %"]<0),
               (b["Price Chg %"]<0)&(b["OI Chg %"]<0)],
              ["LB","SB","SC","LU"],default="Flat/Mixed")

            if "Tot PE OI Chg %" not in b.columns: b["Tot PE OI Chg %"]=np.nan
            if "Tot CE OI Chg %" not in b.columns: b["Tot CE OI Chg %"]=np.nan
            b["options_oi_state"]=np.select(
                [b["Tot PE OI Chg %"]>b["Tot CE OI Chg %"],
                 b["Tot PE OI Chg %"]<b["Tot CE OI Chg %"]],
                ["PE-OI dominant","CE-OI dominant"],default="Balanced")

            if "Volume Chg (%)" not in b.columns:
                sc=[c for c in b.columns if c=="spikes__Volume Chg (%)"]
                b["Volume Chg (%)"]=b[sc[0]].map(num) if sc else np.nan
            b["volume_confirmation"]=np.select(
                [(b["Price Chg %"]>0)&(b["Volume Chg (%)"]>0),
                 (b["Price Chg %"]<0)&(b["Volume Chg (%)"]>0)],
                ["Up+Volume","Down+Volume"],default="Weak/Neutral")

            if "VWAP" not in b.columns: b["VWAP"]=np.nan
            if "Close" not in b.columns: b["Close"]=np.nan
            b["vwap_relation"]=np.select(
                [b["Close"]>b["VWAP"],b["Close"]<b["VWAP"]],
                ["Above VWAP","Below VWAP"],default="VWAP unavailable/neutral")

            if "MWPL (%)" not in b.columns: b["MWPL (%)"]=np.nan
            b["mwpl_state"]=pd.cut(
                b["MWPL (%)"],[-np.inf,60,70,80,90,np.inf],
                labels=["<60","60-70","70-80","80-90",">=90"],right=False
            ).astype(object).where(b["MWPL (%)"].notna(),"MWPL unavailable")

            if "IVP" not in b.columns: b["IVP"]=np.nan
            b["iv_regime"]=np.select(
                [b["IVP"]>=80,b["IVP"]>=50,b["IVP"]<=20],
                ["High IVP","Mid IVP","Low IVP"],default="Normal IVP")

            b["market_state_key"]=(
                b["futures_positioning"].fillna("")+"|"+
                b["options_oi_state"].fillna("")+"|"+
                b["volume_confirmation"].fillna("")+"|"+
                b["vwap_relation"].fillna("")+"|"+
                b["mwpl_state"].fillna("")+"|"+
                b["iv_regime"].fillna("")
            )
            all_rows.append(b)

    out=pd.concat(all_rows,ignore_index=True) if all_rows else pd.DataFrame()
    if not out.empty:
        out["snapshot_time"]=pd.to_datetime(out["snapshot_time"],errors="coerce")
        out=out.sort_values(["Symbol","snapshot_time"]).drop_duplicates(["Symbol","snapshot_time"],keep="last")
    return out,pd.DataFrame(inputs)
