import json
from pathlib import Path
import pandas as pd

def main():
    c=json.loads(Path("CONFIG.json").read_text(encoding="utf-8"))
    src=Path(c["market_state_report"]); out=Path(c["market_state_cache"])
    out.parent.mkdir(parents=True,exist_ok=True)
    if not src.exists(): raise FileNotFoundError(src)
    x=pd.ExcelFile(src)
    sizes={s:len(pd.read_excel(src,sheet_name=s)) for s in x.sheet_names}
    sheet=max(sizes,key=sizes.get)
    d=pd.read_excel(src,sheet_name=sheet)
    d.columns=[str(c).strip() for c in d.columns]
    low={str(c).lower():c for c in d.columns}
    def pick(*n):
        for x in n:
            if x.lower() in low:return low[x.lower()]
    sym=pick("Symbol","_symbol")
    ts=pick("Snapshot Time","Snapshot","snapshot_time","Timestamp","Market Time","Time")
    if not sym or not ts: raise ValueError("Symbol/timestamp column not found")
    d["_symbol"]=d[sym].astype(str).str.strip()
    d["_ts"]=pd.to_datetime(d[ts],errors="coerce")
    d=d.dropna(subset=["_symbol","_ts"]).sort_values(["_symbol","_ts"])
    d=d.drop_duplicates(["_symbol","_ts"],keep="last")
    d["snapshot_time"]=d["_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
    d["market_date"]=d["_ts"].dt.strftime("%Y-%m-%d")
    d.drop(columns=["_ts"],inplace=True)
    d.to_csv(out,index=False)
    meta={"status":"SUCCESS","source":str(src),"sheet":sheet,"rows":len(d),
          "symbols":d["_symbol"].nunique(),"snapshots":d["snapshot_time"].nunique(),
          "cache":str(out)}
    out.with_suffix(".metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta,separators=(",",":")))
if __name__=="__main__": main()
