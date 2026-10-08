from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import math
import pandas as pd

PIT_WINDOWS=(15,30,60,120,240,390)
HISTORY_DAYS=(5,10,20)

@dataclass(frozen=True)
class UUAConfig:
    pit_windows: tuple[int,...]=PIT_WINDOWS
    history_days: tuple[int,...]=HISTORY_DAYS
    ratio_threshold: float=2.0
    robust_z_threshold: float=2.0
    same_time_tolerance_minutes: int=7
    min_samples: int=3
    min_absolute_change: float=0.0
    min_baseline: float=0.0

# Absolute and percentage change fields are deliberately separate.  Do not
# alias a percentage field to its absolute-change counterpart.
ALIASES={
"PE_OI":("pe_oi","PE OI","Tot PE OI","Total PE OI","Put OI"),
"CE_OI":("ce_oi","CE OI","Tot CE OI","Total CE OI","Call OI"),
"PE_MINUS_CE_OI":("__PE_MINUS_CE_OI","pe_minus_ce_oi","PE-CE OI","PE−CE OI","Tot PE-CE OI","PE CE OI","pece_value","PECE Value","PECE"),
"FUTURES_OI":("futures_oi","Futures OI","Future OI","Fut OI","total_oi","Futures Open Interest"),
"VOLUME":("volume","Volume","Vol","traded_volume","Traded Volume"),
"PRICE":("price","Price","Close","current_price","LTP","Last Price","Spot Price"),
"IV":("iv","IV","Implied Volatility","ATM IV","Implied Vol"),
"PCR":("pcr","PCR","Put Call Ratio","Put-Call Ratio"),
"PE_OI_CHANGE":("__PE_OI_CHANGE","pe_oi_chg","pe_oi_change","PE OI Chg","PE OI Change","Tot PE OI Chg","Tot PE OI Change"),
"PE_OI_CHANGE_PCT":("__PE_OI_CHANGE_PCT","pe_oi_chg_pct","pe_oi_change_pct","PE OI Chg %","PE OI Change %","Tot PE OI Chg %","Tot PE OI Change %"),
"CE_OI_CHANGE":("__CE_OI_CHANGE","ce_oi_chg","ce_oi_change","CE OI Chg","CE OI Change","Tot CE OI Chg","Tot CE OI Change"),
"CE_OI_CHANGE_PCT":("__CE_OI_CHANGE_PCT","ce_oi_chg_pct","ce_oi_change_pct","CE OI Chg %","CE OI Change %","Tot CE OI Chg %","Tot CE OI Change %"),
"PE_MINUS_CE_OI_CHANGE":("__PE_MINUS_CE_OI_CHANGE","pe_minus_ce_oi_chg","pe_minus_ce_oi_change","PE-CE OI Chg","PE-CE OI Change","PE−CE OI Change","Tot PE-CE OI Chg","Tot PE-CE OI Change"),
"PE_MINUS_CE_OI_CHANGE_PCT":("__PE_MINUS_CE_OI_CHANGE_PCT","pe_minus_ce_oi_chg_pct","pe_minus_ce_oi_change_pct","pece_change_pct","pe_ce_change_pct","PE-CE OI Chg %","PE-CE OI Change %","PE−CE OI Change %","Tot PE-CE OI Chg %","Tot PE-CE OI Change %"),
"CE_MINUS_PE_OI_CHANGE":("__CE_MINUS_PE_OI_CHANGE","ce_minus_pe_oi_chg","ce_minus_pe_oi_change","CE-PE OI Chg","CE-PE OI Change","CE−PE OI Chg","CE−PE OI Change"),
"FUTURES_OI_CHANGE":("__FUTURES_OI_CHANGE","futures_oi_chg","futures_oi_change","Futures OI Chg","Futures OI Change","Fut OI Chg","Fut OI Change","futures_oi_delta"),
"FUTURES_OI_CHANGE_PCT":("__FUTURES_OI_CHANGE_PCT","futures_oi_chg_pct","futures_oi_change_pct","Futures OI Chg %","Futures OI Change %","Fut OI Chg %","Fut OI Change %","Futures OI Δ %","fut_oi_change_pct"),
"VOLUME_CHANGE":("__VOLUME_CHANGE","volume_chg","volume_change","Volume Chg","Volume Change","Traded Volume Change"),
"VOLUME_CHANGE_PCT":("__VOLUME_CHANGE_PCT","volume_chg_pct","volume_change_pct","Volume Chg %","Volume Change %","volume_pct_change"),
"PRICE_CHANGE":("__PRICE_CHANGE","price_chg","price_change","Price Chg","Price Change"),
"PRICE_CHANGE_PCT":("__PRICE_CHANGE_PCT","price_chg_pct","price_change_pct","Price Chg %","Price Change %","price_pct_change"),
"IV_CHANGE":("__IV_CHANGE","iv_chg","iv_change","IV Chg","IV Change"),
"IV_CHANGE_PCT":("__IV_CHANGE_PCT","iv_chg_pct","iv_change_pct","IV Chg %","IV Change %","iv_pct_change"),
"PCR_CHANGE":("__PCR_CHANGE","pcr_chg","pcr_change","PCR Chg","PCR Change"),
"PCR_CHANGE_PCT":("__PCR_CHANGE_PCT","pcr_chg_pct","pcr_change_pct","PCR Chg %","PCR Change %","pcr_pct_change"),
}
LABELS={k:k.replace("_"," ") for k in ALIASES}
LABELS.update({
"PE_MINUS_CE_OI":"PE−CE OI",
"PE_OI_CHANGE":"PE OI Change","PE_OI_CHANGE_PCT":"PE OI Change %",
"CE_OI_CHANGE":"CE OI Change","CE_OI_CHANGE_PCT":"CE OI Change %",
"PE_MINUS_CE_OI_CHANGE":"PE−CE OI Change","PE_MINUS_CE_OI_CHANGE_PCT":"PE−CE OI Change %",
"CE_MINUS_PE_OI_CHANGE":"CE−PE OI Change",
"FUTURES_OI":"Futures OI","FUTURES_OI_CHANGE":"Futures OI Change","FUTURES_OI_CHANGE_PCT":"Futures OI Change %",
"VOLUME_CHANGE":"Volume Change","VOLUME_CHANGE_PCT":"Volume Change %",
"PRICE_CHANGE":"Price Change","PRICE_CHANGE_PCT":"Price Change %",
"IV_CHANGE":"IV Change","IV_CHANGE_PCT":"IV Change %",
"PCR_CHANGE":"PCR Change","PCR_CHANGE_PCT":"PCR Change %"})

# Ratio/expansion metrics.  Price/PCR/IV change fields use differences or
# percentage change, not a blind value ratio.
RATIO_METRICS={"PE_OI","CE_OI","PE_MINUS_CE_OI","FUTURES_OI","VOLUME"}
OUT_COLS=("symbol","metric","metric_key","event","current_timestamp","current_value","baseline_value","absolute_change","percent_change","ratio","robust_z","comparison_count","comparison_window","reference","unusual","low_base","scope")


def _scalar(x):
    if isinstance(x,pd.DataFrame): return x.iloc[0,0] if x.shape[0] and x.shape[1] else None
    if isinstance(x,pd.Series): return x.iloc[0] if len(x) else None
    if isinstance(x,(list,tuple)): return x[0] if x else None
    return x

def _num(x):
    x=_scalar(x)
    if x is None or isinstance(x,(pd.Timestamp,dict,set)): return None
    try:
        m=pd.isna(x)
        if isinstance(m,bool) and m: return None
    except Exception: pass
    try:
        y=float(str(x).replace(",","").replace("%","").strip())
        return y if math.isfinite(y) else None
    except Exception: return None

def _norm(x):
    return " ".join(str(x).strip().lower().replace("−","-").replace("%"," pct ").replace("_"," ").split())

def _find(d,aliases):
    if not isinstance(d,pd.DataFrame): return None
    wanted={_norm(a) for a in aliases}
    for c in d.columns:
        if _norm(c) in wanted: return c
    return None

def _prepare(frame):
    if not isinstance(frame,pd.DataFrame) or frame.empty:return pd.DataFrame()
    d=frame.copy();d=d.loc[:,~pd.Index(d.columns).duplicated(keep="first")].copy()
    sym=_find(d,("symbol","Symbol","ticker","Ticker"));ts=_find(d,("source_timestamp","observation_timestamp","timestamp","observed_at","observation_time"));dt=_find(d,("trading_date","trade_date","date"))
    if sym is None or ts is None:return pd.DataFrame()
    d["_symbol"]=d[sym].map(lambda x:str(_scalar(x)).strip().upper())
    d["_ts"]=pd.to_datetime(d[ts],errors="coerce")
    d["_date"]=pd.to_datetime(d[dt],errors="coerce").dt.date if dt is not None else d["_ts"].dt.date
    d=d.loc[d["_ts"].notna() & d["_date"].notna()].sort_values(["_symbol","_ts"]).reset_index(drop=True)
    # Derived evidence fields are created only when the source does not already
    # provide the field.  They never enter SDL selection/ranking.
    for base_key,chg_key,pct_key in (("PE_OI","PE_OI_CHANGE","PE_OI_CHANGE_PCT"),("CE_OI","CE_OI_CHANGE","CE_OI_CHANGE_PCT"),("VOLUME","VOLUME_CHANGE","VOLUME_CHANGE_PCT"),("PRICE","PRICE_CHANGE","PRICE_CHANGE_PCT"),("IV","IV_CHANGE","IV_CHANGE_PCT"),("PCR","PCR_CHANGE","PCR_CHANGE_PCT"),("FUTURES_OI","FUTURES_OI_CHANGE","FUTURES_OI_CHANGE_PCT")):
        base=_find(d,ALIASES[base_key])
        if base is None: continue
        if _find(d,ALIASES[chg_key]) is None:d["__"+chg_key]=d.groupby("_symbol",sort=False)[base].diff()
        if _find(d,ALIASES[pct_key]) is None:d["__"+pct_key]=d.groupby("_symbol",sort=False)[base].pct_change(fill_method=None)*100.0
    pe=_find(d,ALIASES["PE_OI"]);ce=_find(d,ALIASES["CE_OI"])
    if _find(d,ALIASES["PE_MINUS_CE_OI"]) is None and pe is not None and ce is not None:d["__PE_MINUS_CE_OI"]=pd.to_numeric(d[pe],errors="coerce")-pd.to_numeric(d[ce],errors="coerce")
    pece=_find(d,ALIASES["PE_MINUS_CE_OI"])
    if pece is not None:
        if _find(d,ALIASES["PE_MINUS_CE_OI_CHANGE"]) is None:d["__PE_MINUS_CE_OI_CHANGE"]=d.groupby("_symbol",sort=False)[pece].diff()
        if _find(d,ALIASES["PE_MINUS_CE_OI_CHANGE_PCT"]) is None:d["__PE_MINUS_CE_OI_CHANGE_PCT"]=d.groupby("_symbol",sort=False)[pece].pct_change(fill_method=None)*100.0
    # Canonical trader-facing options change is CE minus PE. If the source
    # exposes PE-minus-CE, invert the sign; if it exposes CE-minus-PE, preserve it.
    cepe=_find(d,ALIASES["CE_MINUS_PE_OI_CHANGE"])
    if cepe is None:
        raw_pece=_find(d,ALIASES["PE_MINUS_CE_OI_CHANGE"])
        if raw_pece is not None:
            d["__CE_MINUS_PE_OI_CHANGE"]=-pd.to_numeric(d[raw_pece],errors="coerce")
        elif pece is not None:
            d["__CE_MINUS_PE_OI_CHANGE"]= -d.groupby("_symbol",sort=False)[pece].diff()
    return d

def available_metrics(frame):
    d=_prepare(frame)
    return [m for m,a in ALIASES.items() if _find(d,a) is not None]

def _latest(frame,timestamp=None):
    d=_prepare(frame)
    if d.empty:return d,None
    ts=pd.to_datetime(timestamp,errors="coerce") if timestamp is not None else d["_ts"].max()
    if pd.isna(ts):return d.iloc[0:0],None
    ts=pd.Timestamp(ts)
    same=d.loc[d["_date"].eq(ts.date())].copy()
    if same.empty:return d.iloc[0:0],ts
    delta=(same["_ts"]-ts).abs();idx=delta.idxmin();actual=pd.Timestamp(same.loc[idx,"_ts"])
    return same.loc[same["_ts"].eq(actual)].copy(),actual

def _normalize_metrics(metrics, frame):
    """Normalize UI metric selections to a plain Python list.

    Never evaluate a pandas Series/DataFrame in boolean context; an empty
    selection falls back explicitly to the source-capable metric catalogue.
    """
    if metrics is None:
        return list(available_metrics(frame))
    if isinstance(metrics, pd.DataFrame):
        if metrics.shape[1] == 1:
            return [v for v in metrics.iloc[:, 0].tolist() if v is not None]
        return [v for v in metrics.to_numpy().ravel().tolist() if v is not None]
    if isinstance(metrics, pd.Series):
        return [v for v in metrics.tolist() if v is not None]
    if isinstance(metrics, (list, tuple, set)):
        return list(metrics)
    return [metrics]


def _stats(value,history,metric,cfg):
    vals=[_num(x) for x in history];vals=[x for x in vals if x is not None]
    if not vals:return None,None,None,None,None,False,True
    s=pd.Series(vals,dtype="float64");med=float(s.median());mean=float(s.mean());p90=float(s.quantile(.9));base=abs(med)
    low=base<=max(float(cfg.min_baseline),float(cfg.min_absolute_change),1e-12)
    ratio=None if base==0 else abs(value)/base;pct=None if base==0 else (value-med)/base*100
    mad=float((s-s.median()).abs().median());z=None if mad==0 or len(s)<2 else .6745*abs(value-med)/mad
    if metric in RATIO_METRICS: unusual=len(vals)>=cfg.min_samples and not low and ratio is not None and ratio>=cfg.ratio_threshold and abs(value-med)>=cfg.min_absolute_change
    else: unusual=len(vals)>=cfg.min_samples and not low and ((z is not None and abs(z)>=cfg.robust_z_threshold) or (pct is not None and abs(pct)>=cfg.ratio_threshold*100)) and abs(value-med)>=cfg.min_absolute_change
    return med,mean,p90,ratio,z,bool(unusual),bool(low)

def _acceleration_stats(value,history,cfg):
    vals=[_num(x) for x in history if _num(x) is not None]
    if len(vals)<2:return None,None,None,None,None,False,True
    s=pd.Series(vals,dtype="float64");steps=s.diff().dropna();
    if steps.empty:return None,None,None,None,None,False,True
    base=float(steps.abs().median());delta=value-float(s.iloc[-1]);ratio=None if base==0 else abs(delta)/base
    pct=None if s.iloc[-1]==0 else delta/abs(float(s.iloc[-1]))*100
    mad=float((steps.abs()-steps.abs().median()).abs().median());z=None if mad==0 else .6745*abs(abs(delta)-steps.abs().median())/mad
    low=base<=max(float(cfg.min_baseline),float(cfg.min_absolute_change),1e-12)
    unusual=len(steps)>=cfg.min_samples and not low and ratio is not None and ratio>=cfg.ratio_threshold and abs(delta)>=cfg.min_absolute_change
    return float(s.iloc[-1]),base,delta,ratio,z,bool(unusual),bool(low)

def _rows(current,history,metrics,cfg,window,reference,event,scope):
    rows=[]
    for metric in metrics:
        cc=_find(current,ALIASES[metric]);hc=_find(history,ALIASES[metric])
        if cc is None or hc is None:continue
        for _,cur in current.iterrows():
            value=_num(cur[cc]);
            if value is None:continue
            vals=[_num(v) for v in history.loc[history["_symbol"].eq(cur["_symbol"]),hc].tolist()];vals=[v for v in vals if v is not None]
            if str(event).upper()=="ACCELERATION":
                med,base,delta,ratio,z,unusual,low=_acceleration_stats(value,vals,cfg);absolute=delta;percent=None if med in (None,0) else delta/abs(med)*100
            else:
                med,mean,p90,ratio,z,unusual,low=_stats(value,vals,metric,cfg);absolute=None if med is None else value-med;percent=None if med in (None,0) else (value-med)/abs(med)*100
            rows.append({"symbol":cur["_symbol"],"metric":LABELS[metric],"metric_key":metric,"event":event,"current_timestamp":cur["_ts"],"current_value":value,"baseline_value":med,"absolute_change":absolute,"percent_change":percent,"ratio":ratio,"robust_z":z,"comparison_count":len(vals),"comparison_window":window,"reference":reference,"unusual":unusual,"low_base":low,"scope":scope})
    return pd.DataFrame(rows,columns=OUT_COLS)

def build_pit_uua(frame,timestamp=None,config=None,scope="LIVE QUEUE",metrics=None,event_mode="EXPANSION",window_minutes=15):
    cfg=config or UUAConfig();d=_prepare(frame);current,ts=_latest(d,timestamp)
    if current.empty:return pd.DataFrame(columns=OUT_COLS)
    start=ts-pd.Timedelta(minutes=int(window_minutes));hist=d.loc[(d["_date"].eq(ts.date())) & (d["_ts"]>=start) & (d["_ts"]<ts)].copy()
    return _rows(current,hist,_normalize_metrics(metrics, d),cfg,f"{window_minutes}M","TODAY PIT",event_mode,scope)

def flatten_cache(cache,trading_date=None):
    """Flatten only persisted logical replay snapshots, never timeline/PIT metadata.

    This is the performance boundary for UUA: a replay cache may contain large
    auxiliary structures, but UUA needs the authoritative logical::<timestamp>
    frames only.
    """
    if isinstance(cache,pd.DataFrame):
        return _prepare(cache)
    if not isinstance(cache,Mapping):
        return pd.DataFrame()
    snapshots=cache.get("snapshots")
    frames=[]
    if isinstance(snapshots,Mapping):
        for key,value in snapshots.items():
            if str(key).startswith("logical::") and isinstance(value,pd.DataFrame) and not value.empty:
                f=value.copy()
                if trading_date and _find(f,("trading_date","trade_date","date")) is None:
                    f["trading_date"]=trading_date
                frames.append(f)
    if not frames:
        return pd.DataFrame()
    return _prepare(pd.concat(frames,ignore_index=True))

def _day_value(d,metric,symbol,first):
    x=d.loc[d["_symbol"].eq(symbol)].sort_values("_ts");col=_find(x,ALIASES[metric])
    if x.empty or col is None:return None
    return _num(x.iloc[0 if first else -1][col])

def _ref_row(symbol,metric,value,base,ts,window,reference,cfg,scope):
    if base is None or value is None:return None
    delta=value-base;pct=None if base==0 else delta/abs(base)*100;ratio=None if base==0 else abs(value)/abs(base)
    low=abs(base)<=max(cfg.min_baseline,cfg.min_absolute_change,1e-12)
    unusual=bool(not low and ((metric in RATIO_METRICS and ratio is not None and ratio>=cfg.ratio_threshold) or (metric not in RATIO_METRICS and pct is not None and abs(pct)>=cfg.ratio_threshold*100)) and abs(delta)>=cfg.min_absolute_change)
    return {"symbol":symbol,"metric":LABELS[metric],"metric_key":metric,"event":"EXPANSION","current_timestamp":ts,"current_value":value,"baseline_value":base,"absolute_change":delta,"percent_change":pct,"ratio":ratio,"robust_z":None,"comparison_count":1,"comparison_window":window,"reference":reference,"unusual":unusual,"low_base":low,"scope":scope}

def _value_to_time(d, metric, symbol, target_ts):
    x = d.loc[d["_symbol"].eq(symbol)].sort_values("_ts")
    if x.empty:
        return None
    col = _find(x, ALIASES[metric])
    if col is None:
        return None
    target = pd.Timestamp(target_ts)
    x = x.loc[x["_ts"] <= target]
    if x.empty:
        return None
    vals = [_num(v) for v in x[col].tolist()]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    # Cumulative/activity fields use their latest state at the cut-off.
    # Explicit change fields are accumulated over the elapsed session.
    if metric in {"VOLUME_CHANGE", "PE_OI_CHANGE", "CE_OI_CHANGE", "PE_MINUS_CE_OI_CHANGE", "FUTURES_OI_CHANGE"}:
        return float(sum(vals))
    return float(vals[-1])


def _day_elapsed_target(day_frame, today_first_ts, today_target_ts):
    if day_frame.empty:
        return None
    first = day_frame["_ts"].min()
    elapsed = max(pd.Timestamp(today_target_ts) - pd.Timestamp(today_first_ts), pd.Timedelta(0))
    return pd.Timestamp(first) + elapsed


def build_day_start_uua(frame, historical_caches, timestamp=None, config=None, scope="LIVE QUEUE", metrics=None):
    """Compare today's cumulative-to-current-time state with prior days at the same elapsed session point.

    This is deliberately different from SAME-TIME: DAY START / CUMULATIVE aligns
    the elapsed session from each day's first valid observation, while SAME-TIME
    aligns the wall-clock timestamp.
    """
    cfg = config or UUAConfig()
    d = _prepare(frame)
    current, ts = _latest(d, timestamp)
    if current.empty:
        return pd.DataFrame(columns=OUT_COLS)
    dates = sorted([str(k) for k in historical_caches], reverse=True)
    history_frames = {day: flatten_cache(historical_caches[day], day) for day in dates}
    metrics = _normalize_metrics(metrics, d)
    rows = []
    today_first = d["_ts"].min()
    for metric in metrics:
        cc = _find(current, ALIASES[metric])
        if cc is None:
            continue
        for _, cur in current.iterrows():
            value = _num(cur[cc])
            if value is None:
                continue
            symbol = cur["_symbol"]
            # Opening-state reference remains useful for the selected stock.
            opening = _value_to_time(d, metric, symbol, today_first)
            row = _ref_row(symbol, metric, value, opening, ts, "DAY START", "TODAY OPEN", cfg, scope)
            if row:
                rows.append(row)
            hist_values = []
            for day in dates:
                h = history_frames.get(day, pd.DataFrame())
                if h.empty:
                    continue
                target = _day_elapsed_target(h, today_first, ts)
                if target is None:
                    continue
                v = _value_to_time(h, metric, symbol, target)
                if v is not None:
                    hist_values.append(v)
            if hist_values:
                med, mean, p90, ratio, z, unusual, low = _stats(value, hist_values, metric, cfg)
                rows.append({
                    "symbol": symbol, "metric": LABELS[metric], "metric_key": metric,
                    "event": "EXPANSION", "current_timestamp": ts,
                    "current_value": value, "baseline_value": med,
                    "absolute_change": None if med is None else value - med,
                    "percent_change": None if med in (None, 0) else (value - med) / abs(med) * 100,
                    "ratio": ratio, "robust_z": z,
                    "comparison_count": len(hist_values),
                    "comparison_window": "DAY START / CUMULATIVE TO CURRENT TIME",
                    "reference": f"HIST {len(hist_values)}D TO SAME ELAPSED TIME",
                    "unusual": unusual, "low_base": low, "scope": scope,
                })
    return pd.DataFrame(rows, columns=OUT_COLS)

def build_same_time_uua(frame,historical_caches,timestamp=None,days=5,config=None,scope="LIVE QUEUE",metrics=None):
    cfg=config or UUAConfig();d=_prepare(frame);current,ts=_latest(d,timestamp)
    if current.empty:return pd.DataFrame(columns=OUT_COLS)
    dates=sorted([str(k) for k in historical_caches],reverse=True)[:int(days)];rows=[];target=ts.hour*3600+ts.minute*60+ts.second
    history_frames={day:flatten_cache(historical_caches[day],day) for day in dates}
    for day in dates:
        h=history_frames.get(day,pd.DataFrame())
        if h.empty:continue
        hsec=h["_ts"].dt.hour*3600+h["_ts"].dt.minute*60+h["_ts"].dt.second
        for metric in _normalize_metrics(metrics, d):
            cc=_find(current,ALIASES[metric]);hc=_find(h,ALIASES[metric]);
            if cc is None or hc is None:continue
            for _,cur in current.iterrows():
                x=h.loc[h["_symbol"].eq(cur["_symbol"])].copy();
                if x.empty:continue
                delta=(hsec.loc[x.index]-target).abs();idx=delta.idxmin()
                if float(delta.loc[idx])>cfg.same_time_tolerance_minutes*60:continue
                row=_ref_row(cur["_symbol"],metric,_num(cur[cc]),_num(x.loc[idx,hc]),ts,f"SAME-TIME {day}",day,cfg,scope)
                if row:rows.append(row)
    return pd.DataFrame(rows,columns=OUT_COLS)

def _full_day_value(d,metric,symbol):
    x=d.loc[d["_symbol"].eq(symbol)].sort_values("_ts");col=_find(x,ALIASES[metric])
    if x.empty or col is None:return None
    vals=[_num(v) for v in x[col].tolist()];vals=[v for v in vals if v is not None]
    if not vals:return None
    if metric in {"VOLUME","VOLUME_CHANGE"}: return float(vals[-1]) if metric=="VOLUME" and all(vals[i]>=vals[i-1] for i in range(1,len(vals))) else float(sum(vals))
    if metric.endswith("_CHANGE") and metric not in RATIO_METRICS:return float(sum(vals))
    if metric.endswith("_CHANGE_PCT"):return float(sum(vals))
    return float(vals[-1])

def build_eod_uua(frame,historical_caches,timestamp=None,config=None,scope="LIVE QUEUE",metrics=None,days=5):
    cfg=config or UUAConfig();d=_prepare(frame);current,ts=_latest(d,timestamp)
    if current.empty:return pd.DataFrame(columns=OUT_COLS)
    dates=sorted([str(k) for k in historical_caches],reverse=True)[:int(days)];rows=[]
    history_frames={day:flatten_cache(historical_caches[day],day) for day in dates}
    for metric in _normalize_metrics(metrics, d):
        cc=_find(current,ALIASES[metric]);
        if cc is None:continue
        for _,cur in current.iterrows():
            value=_num(cur[cc]);
            if value is None:continue
            vals=[]
            for day in dates:
                h=history_frames.get(day,pd.DataFrame())
                v=_full_day_value(h,metric,cur["_symbol"]) if not h.empty else None
                if v is not None:vals.append(v)
            med,mean,p90,ratio,z,unusual,low=_stats(value,vals,metric,cfg)
            rows.append({"symbol":cur["_symbol"],"metric":LABELS[metric],"metric_key":metric,"event":"EXPANSION","current_timestamp":ts,"current_value":value,"baseline_value":med,"absolute_change":None if med is None else value-med,"percent_change":None if med in (None,0) else (value-med)/abs(med)*100,"ratio":ratio,"robust_z":z,"comparison_count":len(vals),"comparison_window":f"FULL-DAY vs {len(vals)}D EOD","reference":"HISTORICAL FULL-DAY","unusual":unusual,"low_base":low,"scope":scope})
    return pd.DataFrame(rows,columns=OUT_COLS)

# ---------------------------------------------------------------------------
# Historical Change Comparison V1
# ---------------------------------------------------------------------------
# Trader-facing UUA compares CHANGE values only. It never compares absolute
# PE OI / CE OI / Futures OI balances. Options are represented only as
# CE−PE OI CHANGE; Futures uses Futures OI CHANGE %. Historical references are
# prior-session EOD change values (1D) and the maximum absolute change over the
# prior 3/5/10/20 completed sessions.
CHANGE_COMPARE_METRICS = (
    "FUTURES_OI_CHANGE_PCT",
    "CE_MINUS_PE_OI_CHANGE",
)
CHANGE_COMPARE_HORIZONS = (1, 3, 5, 10, 20)
CHANGE_COMPARE_COLUMNS = (
    "symbol", "direction", "metric_key", "metric", "current_timestamp", "current_value",
    "previous_eod_value", "ratio_last", "ratio_3d_max", "ratio_5d_max",
    "ratio_10d_max", "ratio_20d_max", "max_3d_value", "max_5d_value",
    "max_10d_value", "max_20d_value", "new_3d", "new_5d", "new_10d",
    "new_20d", "comparison_days", "grade", "scope",
)


def _change_value_at_eod(day_frame: pd.DataFrame, metric: str, symbol: str):
    if not isinstance(day_frame, pd.DataFrame) or day_frame.empty:
        return None
    x = day_frame.loc[day_frame["_symbol"].eq(symbol)].sort_values("_ts")
    col = _find(x, ALIASES[metric])
    if x.empty or col is None:
        return None
    for value in reversed(x[col].tolist()):
        value = _num(value)
        if value is not None:
            return value
    return None


def _ratio_to_reference(value, reference):
    if value is None or reference is None:
        return None
    ref = abs(float(reference))
    if ref <= 1e-12:
        return None
    return abs(float(value)) / ref


def _grade_change_event(ratios, new_flags):
    r = [float(x) for x in ratios if x is not None]
    if bool(new_flags.get("new_20d")) or any(x >= 4.0 for x in r):
        return "STRONGEST"
    if bool(new_flags.get("new_10d")) or any(x >= 3.0 for x in r):
        return "VERY STRONG"
    if bool(new_flags.get("new_5d")) or bool(new_flags.get("new_3d")) or any(x >= 2.0 for x in r):
        return "STRONG"
    if any(x >= 1.5 for x in r):
        return "ELEVATED"
    return "NORMAL"


def build_historical_change_comparison(
    frame: pd.DataFrame,
    historical_caches: Mapping[str, Mapping[str, object]],
    timestamp=None,
    config: UUAConfig | None = None,
    scope: str = "ALL TODAY",
) -> pd.DataFrame:
    """Compare today's/replay point CHANGE values with prior EOD CHANGE values.

    1D = immediately previous trading day's EOD change value.
    3D/5D/10D/20D = maximum absolute change value across that many prior
    completed sessions. The returned ratio is magnitude-based; the actual
    signed current value remains visible so direction is never hidden.
    """
    _ = config or UUAConfig()
    d = _prepare(frame)
    current, ts = _latest(d, timestamp)
    if current.empty or ts is None:
        return pd.DataFrame(columns=CHANGE_COMPARE_COLUMNS)

    dates = sorted([str(k) for k in historical_caches], reverse=True)
    history_frames = {day: flatten_cache(historical_caches[day], day) for day in dates}
    rows = []
    for metric in CHANGE_COMPARE_METRICS:
        current_col = _find(current, ALIASES[metric])
        if current_col is None:
            continue
        for _, cur in current.iterrows():
            symbol = cur["_symbol"]
            value = _num(cur.get(current_col))
            if value is None:
                continue
            prior_values = []
            for day in dates:
                v = _change_value_at_eod(history_frames.get(day, pd.DataFrame()), metric, symbol)
                if v is not None:
                    prior_values.append((day, v))
            previous = prior_values[0][1] if prior_values else None
            max_values = {}
            new_flags = {}
            ratios = [_ratio_to_reference(value, previous)]
            for horizon in (3, 5, 10, 20):
                vals = [v for _, v in prior_values[:horizon]]
                maximum = max(vals, key=lambda x: abs(x)) if vals else None
                max_values[horizon] = maximum
                new_flags[f"new_{horizon}d"] = bool(
                    maximum is not None and abs(value) > abs(maximum)
                )
                ratio = _ratio_to_reference(value, maximum)
                ratios.append(ratio)
            grade = _grade_change_event(ratios, new_flags)
            direction = ""
            for dcol in ("decision_direction", "direction", "directional_interpretation", "bias_category"):
                if dcol in cur.index:
                    direction = str(cur.get(dcol) or "").strip().upper()
                    if direction:
                        break
            rows.append({
                "symbol": symbol,
                "direction": direction,
                "metric_key": metric,
                "metric": LABELS.get(metric, metric),
                "current_timestamp": ts,
                "current_value": value,
                "previous_eod_value": previous,
                "ratio_last": _ratio_to_reference(value, previous),
                "ratio_3d_max": _ratio_to_reference(value, max_values[3]),
                "ratio_5d_max": _ratio_to_reference(value, max_values[5]),
                "ratio_10d_max": _ratio_to_reference(value, max_values[10]),
                "ratio_20d_max": _ratio_to_reference(value, max_values[20]),
                "max_3d_value": max_values[3],
                "max_5d_value": max_values[5],
                "max_10d_value": max_values[10],
                "max_20d_value": max_values[20],
                "new_3d": new_flags["new_3d"],
                "new_5d": new_flags["new_5d"],
                "new_10d": new_flags["new_10d"],
                "new_20d": new_flags["new_20d"],
                "comparison_days": len(prior_values),
                "grade": grade,
                "scope": scope,
            })
    return pd.DataFrame(rows, columns=CHANGE_COMPARE_COLUMNS)
