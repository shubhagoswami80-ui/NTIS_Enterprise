from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
OUT = ROOT / ".sector_intelligence" / "v12_7_cumulative_forensics"
OUT.mkdir(parents=True, exist_ok=True)

V8 = [
    "orb_minutes","maturity","orb_dir","price_dir","fut_dir","option_dir",
    "fut_state","volume_state","ce_state","pe_state","pec_state","fut_oi_state",
    "ce_pct_state","pe_pct_state","pec_pct_state","fut_pct_state","price_state",
    "orb_agree","evidence_agreement","persistent","strength_bucket",
    "core_count_band","magnitude_count_band","orb_fut_agree","orb_price_agree",
]
TRAJ = ["px_all_negative_pre_maturity","px_all_positive_pre_maturity","px_negative_count_pre_maturity"]

EXTS = {".py",".csv",".json",".xlsx",".xls",".parquet",".db",".md"}
DATA_EXTS = {".csv",".json",".xlsx",".xls",".parquet",".db"}
RESEARCH_NAMES = {
    "pattern_population.csv","candidate_catalog.csv","maturity_feature_matrix.csv",
    "chronological_validation.csv","chronological_validation_corrected.csv",
    "phase3b_robust_population.csv","phase3c_top50_robust_for_review.csv",
}
INGEST_RE = re.compile(r"\b(read_csv|read_excel|read_parquet|glob|rglob|Path\(|iterdir|walk|source_root|input_root|data_root|snapshot|current|latest)\b", re.I)
WRITE_RE = re.compile(r"\b(to_csv|to_excel|to_json|to_parquet|write_text|write_bytes|json\.dump|write_result|write_history|write_manifest)\b", re.I)
V8_RE = re.compile("|".join(re.escape(x) for x in V8 + TRAJ), re.I)

def sha1(path):
    h=hashlib.sha1()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def safe_text(path, limit=2_000_000):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""

def classify(path):
    s=str(path).lower()
    n=path.name.lower()
    if n in RESEARCH_NAMES or ".sector_intelligence" in s:
        return "research_or_cache"
    if path.suffix.lower() == ".py":
        return "python"
    return "data_or_document"

files=[p for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in EXTS]

py_rows=[]
field_hits=[]
producer_scores=[]
data_rows=[]

for p in files:
    try:
        st=p.stat()
    except OSError:
        continue
    rel=str(p.relative_to(ROOT))
    kind=classify(p)
    row={
        "path":rel,"name":p.name,"ext":p.suffix.lower(),"size":st.st_size,
        "modified":datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ",timespec="seconds"),
        "class":kind,
    }
    if p.suffix.lower()==".py":
        txt=safe_text(p)
        v8=sorted(set(x for x in V8+TRAJ if re.search(r"\b"+re.escape(x)+r"\b",txt,re.I)))
        ing=sorted(set(m.group(1) for m in INGEST_RE.finditer(txt)))
        wr=sorted(set(m.group(1) for m in WRITE_RE.finditer(txt)))
        score=0
        score += 10*len(v8)
        score += 5*len(ing)
        score += 4*len(wr)
        score += 3*sum(1 for x in ("symbol","stock","trade_date","observed_at") if re.search(r"\b"+x+r"\b",txt,re.I))
        score += 4*sum(1 for x in ("orb","maturity","straddle") if re.search(r"\b"+x+r"\b",txt,re.I))
        # Penalize obvious pure validation/research consumers.
        if any(x in p.name.lower() for x in ("validation","forensics","scanner","study","research","audit","miner")):
            score -= 12
        py_rows.append({**row,"v8_fields":len(v8),"v8_field_names":";".join(v8),
                        "ingestion_tokens":";".join(ing),"write_tokens":";".join(wr),"producer_score":score})
        if v8 or ing or wr:
            for term in sorted(set(v8)):
                for m in re.finditer(r".{0,100}\b"+re.escape(term)+r"\b.{0,180}",txt,re.I|re.S):
                    snippet=" ".join(m.group(0).split())
                    field_hits.append({"path":rel,"field":term,"snippet":snippet[:350]})
                    if len(field_hits)>5000: break
                if len(field_hits)>5000: break
            producer_scores.append((score,rel))
    elif p.suffix.lower() in DATA_EXTS:
        data_rows.append(row)

py_rows.sort(key=lambda x:(x["producer_score"],x["v8_fields"],x["size"]), reverse=True)
data_rows.sort(key=lambda x:x["modified"], reverse=True)

# Inspect headers/keys for manageable text data files.
schema_rows=[]
for r in data_rows:
    p=ROOT/r["path"]
    try:
        if p.suffix.lower()==".csv" and r["size"]<=25_000_000:
            with p.open("r",encoding="utf-8-sig",errors="ignore",newline="") as f:
                reader=csv.reader(f)
                header=next(reader,[])
            schema_rows.append({**r,"schema":";".join(header[:150]),
                                "has_symbol":any(x.strip().lower()=="symbol" for x in header),
                                "v8_header_count":sum(x.strip().lower() in {z.lower() for z in V8} for x in header)})
        elif p.suffix.lower()==".json" and r["size"]<=10_000_000:
            txt=safe_text(p,500_000)
            keys=[]
            try:
                obj=json.loads(txt)
                if isinstance(obj,dict): keys=list(obj.keys())
                elif isinstance(obj,list) and obj and isinstance(obj[0],dict): keys=list(obj[0].keys())
            except Exception:
                pass
            schema_rows.append({**r,"schema":";".join(map(str,keys[:150])),
                                "has_symbol":any(str(x).lower()=="symbol" for x in keys),
                                "v8_header_count":sum(str(x).lower() in {z.lower() for z in V8} for x in keys)})
        else:
            schema_rows.append({**r,"schema":"","has_symbol":"","v8_header_count":""})
    except Exception as e:
        schema_rows.append({**r,"schema":"","has_symbol":"","v8_header_count":"","error":str(e)})

# Save reports.
def write_csv(name, rows):
    path=OUT/name
    if not rows:
        path.write_text("",encoding="utf-8")
        return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys)
        w.writeheader(); w.writerows(rows)

write_csv("python_ranked_producers.csv",py_rows)
write_csv("data_inventory_recent.csv",data_rows)
write_csv("data_schema_and_v8_headers.csv",schema_rows)
write_csv("v8_field_context_hits.csv",field_hits[:5000])

top=py_rows[:30]
candidate_data=[r for r in schema_rows if r.get("has_symbol") or (r.get("v8_header_count") or 0)>0]
summary={
    "root":str(ROOT),
    "generated_at":datetime.now().isoformat(timespec="seconds"),
    "files_scanned":len(files),
    "python_files":sum(p.suffix.lower()==".py" for p in files),
    "data_files":sum(p.suffix.lower() in DATA_EXTS for p in files),
    "top_python_candidates":top,
    "current_like_data_candidates":candidate_data[:100],
    "v8_fields":V8,
    "trajectory_fields":TRAJ,
    "interpretation":"Read-only forensic inventory. No production/dashboard files are modified.",
    "next_decision":"Use highest-ranked non-research producer or current-like data artifact if it can produce one row per symbol/maturity/ORB context; otherwise design a research-only adapter."
}
(OUT/"forensics_summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")

# Human-readable shortlist.
lines=[
"NTIS SDL V12.7 CUMULATIVE FORENSIC REPORT",
"==========================================",
f"Generated: {summary['generated_at']}",
f"Files scanned: {len(files)}",
f"Python files: {summary['python_files']}",
f"Data files: {summary['data_files']}",
"",
"TOP PYTHON CANDIDATES (ranked)",
"------------------------------",
]
for i,r in enumerate(top,1):
    lines.append(f"{i:02d}. SCORE={r['producer_score']:4}  {r['path']}  | V8={r['v8_fields']} | INGEST={r['ingestion_tokens']} | WRITE={r['write_tokens']}")
lines += ["","CURRENT-LIKE DATA CANDIDATES","----------------------------"]
for r in candidate_data[:100]:
    lines.append(f"{r['path']} | modified={r['modified']} | symbol={r['has_symbol']} | V8_HEADERS={r['v8_header_count']} | {r.get('schema','')[:500]}")
lines += ["","IMPORTANT: research/cache files are not treated as current inputs.","No production/dashboard files were modified."]
(OUT/"FORENSIC_REPORT.txt").write_text("\n".join(lines),encoding="utf-8")

print(json.dumps({
    "status":"COMPLETE",
    "files_scanned":len(files),
    "python_files":summary["python_files"],
    "data_files":summary["data_files"],
    "output":str(OUT),
    "top_candidates":[x["path"] for x in top[:15]],
    "current_like_data":[x["path"] for x in candidate_data[:20]]
},indent=2))
