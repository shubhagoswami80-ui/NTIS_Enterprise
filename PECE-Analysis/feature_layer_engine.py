"""
PCR/OI Market-State Feature Layer V1.2
Controlled replacement. Robust datetime normalization + vectorized time alignment.
"""
from pathlib import Path
import json,re
import numpy as np,pandas as pd
BASE=Path(__file__).resolve().parent
CFG=json.loads((BASE/"CONFIG.json").read_text(encoding="utf-8"))
SRC=Path(CFG["source_root"]); ROOT=Path(CFG["output_root"]); OUT=ROOT/"Feature_Layer"; OUT.mkdir(parents=True,exist_ok=True)
REQ=["Time","Fut Price","Fut PriceChg","Fut OI Chg","VWAP","Fut Volume","Tot Fut OI",
"CE Volume","PE Volume","PCR-Volume","TotCE OI","TotPE OI","PCR-OI","CE OI Chg",
"PE OI Chg","Symbol","Snapshot"]
def pos(p,o):
    if pd.isna(p) or pd.isna(o): return "Unknown"
    if p>0 and o>0:return "LB"
    if p<0 and o>0:return "SB"
    if p>0 and o<0:return "SC"
    if p<0 and o<0:return "LU"
    return "Neutral"
def skew(p,v):
    if pd.isna(p) or pd.isna(v) or v<=0:return "Insufficient Activity"
    if p<CFG["strong_ce_pcr_below"]:return "Strong CE Skew"
    if p<CFG["balanced_pcr_low"]:return "Moderate CE Skew"
    if p<=CFG["balanced_pcr_high"]:return "Balanced"
    if p>CFG["strong_pe_pcr_above"]:return "Strong PE Skew"
    return "Moderate PE Skew"
def runlen(s): return s.groupby(s.ne(s.shift()).cumsum()).cumcount()+1
def aligned_past(d,col,minutes):
    out=pd.Series(np.nan,index=d.index,dtype="float64")
    delta=pd.Timedelta(minutes=minutes).value
    for (_, _), idx in d.groupby(["Symbol","_date"],sort=False).groups.items():
        idx=np.asarray(list(idx)); idx=idx[np.argsort(d.loc[idx,"_time"].astype("int64").to_numpy())]
        ts=d.loc[idx,"_time"].astype("int64").to_numpy()
        vals=pd.to_numeric(d.loc[idx,col],errors="coerce").to_numpy(dtype=float)
        target=ts-delta; j=np.searchsorted(ts,target,side="right")-1
        valid=j>=0
        out.loc[idx[valid]]=vals[j[valid]]
    return out
def main():
    files=sorted(SRC.rglob(CFG["source_glob"]))
    if not files: raise FileNotFoundError(f"No source files under {SRC}")
    frames=[]; rejected=[]
    for f in files:
        try:
            x=pd.read_excel(f,sheet_name=CFG["sheet_name"])
            miss=[c for c in REQ if c not in x.columns]
            if miss: rejected.append((str(f),"missing:"+",".join(miss))); continue
            x=x.copy()
            snap=pd.to_datetime(x["Snapshot"].astype(str).str.strip(),format="%Y%m%d_%H%M%S",errors="coerce")
            if snap.isna().all():
                m=re.search(r"PECE_(\d{8}_\d{6})",f.name)
                fb=pd.to_datetime(m.group(1),format="%Y%m%d_%H%M%S",errors="coerce") if m else pd.NaT
                snap=pd.Series(fb,index=x.index)
            # Normalize to naive datetime explicitly. This prevents object dtype
            # when adding date/time components.
            snap=pd.Series(pd.to_datetime(snap,errors="coerce"),index=x.index).dt.tz_localize(None)
            tm=pd.to_datetime(x["Time"].astype(str).str.strip(),format="mixed",errors="coerce")
            tm=pd.Series(pd.to_datetime(tm,errors="coerce"),index=x.index).dt.tz_localize(None)
            base=snap.dt.normalize()
            mins=(tm.dt.hour*60+tm.dt.minute+tm.dt.second/60).fillna(np.nan)
            x["_time"]=pd.to_datetime(base,errors="coerce")+pd.to_timedelta(mins,unit="m")
            x["_source_snapshot"]=snap; x["_source_file"]=str(f)
            frames.append(x)
        except Exception as e: rejected.append((str(f),f"read_error:{e}"))
    if not frames: raise RuntimeError("No valid PECE workbooks.")
    d=pd.concat(frames,ignore_index=True)
    d["Symbol"]=d["Symbol"].astype(str).str.strip().str.upper()
    for c in d.columns:
        if c not in ["Time","Symbol","Snapshot","_source_file","_source_snapshot","_time"]:
            d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["Symbol","_time"]).copy()
    d=d.sort_values(["Symbol","_time","_source_snapshot","_source_file"])
    d=d.drop_duplicates(["Symbol","_time"],keep="last").reset_index(drop=True)
    d["_time"]=pd.to_datetime(d["_time"],errors="coerce")
    d["_date"]=d["_time"].dt.normalize()
    d["_hour"]=d["_time"].dt.hour; d["_minute"]=d["_time"].dt.minute
    d["combined_option_volume"]=d["CE Volume"].fillna(0)+d["PE Volume"].fillna(0)
    d["combined_option_oi"]=d["TotCE OI"].fillna(0)+d["TotPE OI"].fillna(0)
    d["volume_pressure"]=np.where(d["combined_option_volume"]>0,(d["PE Volume"]-d["CE Volume"])/d["combined_option_volume"],np.nan)
    d["oi_pressure"]=np.where(d["combined_option_oi"]>0,(d["TotPE OI"]-d["TotCE OI"])/d["combined_option_oi"],np.nan)
    d["skew_state"]=[skew(a,b) for a,b in zip(d["PCR-Volume"],d["combined_option_volume"])]
    d["futures_position"]=[pos(a,b) for a,b in zip(d["Fut PriceChg"],d["Fut OI Chg"])]
    d["price_vwap_diff_pct"]=np.where(d["VWAP"].notna()&(d["VWAP"]!=0),(d["Fut Price"]-d["VWAP"])/d["VWAP"]*100,np.nan)
    d["vwap_state"]=np.select([d["price_vwap_diff_pct"]>0.10,d["price_vwap_diff_pct"]<-0.10],["Above VWAP","Below VWAP"],default="Near VWAP")
    g=d.groupby("Symbol",sort=False)
    d["prev_skew_state"]=g["skew_state"].shift(); d["prev_futures_position"]=g["futures_position"].shift()
    d["skew_transition"]=d["prev_skew_state"].fillna("NA")+" -> "+d["skew_state"]
    d["position_transition"]=d["prev_futures_position"].fillna("NA")+" -> "+d["futures_position"]
    d["skew_persistence"]=g["skew_state"].transform(runlen); d["position_persistence"]=g["futures_position"].transform(runlen)
    for name,col in [("volume_pressure_delta_15m","volume_pressure"),("oi_pressure_delta_15m","oi_pressure"),
                     ("pcr_volume_delta_15m","PCR-Volume"),("pcr_oi_delta_15m","PCR-OI"),("price_delta_15m","Fut Price")]:
        d[name]=d[col]-aligned_past(d,col,15)
    d["volume_pressure_acceleration"]=d["volume_pressure_delta_15m"]-g["volume_pressure_delta_15m"].shift()
    d["oi_pressure_acceleration"]=d["oi_pressure_delta_15m"]-g["oi_pressure_delta_15m"].shift()
    d["pcr_volume_acceleration"]=d["pcr_volume_delta_15m"]-g["pcr_volume_delta_15m"].shift()
    d["pcr_oi_acceleration"]=d["pcr_oi_delta_15m"]-g["pcr_oi_delta_15m"].shift()
    d["volume_oi_relation"]=np.select([
      (d["volume_pressure"]>0.05)&(d["oi_pressure"]>0.05),
      (d["volume_pressure"]<-0.05)&(d["oi_pressure"]<-0.05),
      (d["volume_pressure"]>0.05)&(d["oi_pressure"]<-0.05),
      (d["volume_pressure"]<-0.05)&(d["oi_pressure"]>0.05)],
      ["PE Confirming","CE Confirming","PE Volume / CE OI Divergence","CE Volume / PE OI Divergence"],default="Neutral")
    d["fut_volume_pct_rank"]=g["Fut Volume"].rank(pct=True); d["option_volume_pct_rank"]=g["combined_option_volume"].rank(pct=True)
    d["activity_state"]=np.select([d["fut_volume_pct_rank"]>=.80,d["fut_volume_pct_rank"]<=.20],["High Futures Activity","Low Futures Activity"],default="Normal Futures Activity")
    d["time_bucket"]=pd.cut(d["_time"].dt.hour+d["_time"].dt.minute/60,bins=[9.4167,10,11,12,13,14,16],
      labels=["09:25-10:00","10:00-11:00","11:00-12:00","12:00-13:00","13:00-14:00","14:00-16:00"],right=False,include_lowest=True).astype(str)
    if "OI ChgTrend" in d.columns:d["oi_chg_trend"]=d["OI ChgTrend"].astype(str).replace("nan",np.nan)
    else:d["oi_chg_trend"]=np.nan
    out=d.sort_values(["_time","Symbol"]).reset_index(drop=True)
    out.to_csv(OUT/"pcr_market_state_features.csv",index=False)
    status={"status":"SUCCESS","workbooks_found":len(files),"valid_workbooks":len(frames),"rejected_workbooks":len(rejected),
      "unique_observations":len(out),"symbols":int(out.Symbol.nunique()),"first_market_time":str(out._time.min()),
      "last_market_time":str(out._time.max()),"dates":sorted(map(str,out._date.dt.date.unique())),"feature_columns":len(out.columns)}
    (OUT/"feature_layer_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    pd.DataFrame(rejected,columns=["source_file","reason"]).to_csv(OUT/"feature_layer_rejections.csv",index=False)
    print(json.dumps(status,separators=(",",":")))
if __name__=="__main__":main()
