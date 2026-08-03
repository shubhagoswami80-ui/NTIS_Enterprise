from pathlib import Path

WORDS=[
"historical","history","similar","similarity",
"evidence","memory","learning",
"pattern","probability","confidence",
"outcome","replay","calibration"
]

def scan_intelligence(root):
    result=[]
    for f in Path(root).rglob("*.py"):
        text=f.read_text(encoding="utf-8",errors="ignore").lower()
        hits=[w for w in WORDS if w in text]
        if hits:
            result.append({"file":str(f),"keywords":hits})
    return result
