from pathlib import Path

def scan_dataflow(root):
    result=[]
    for f in Path(root).rglob("*"):
        if f.is_file() and f.suffix.lower() in [".csv",".xlsx",".json"]:
            result.append(str(f))
    return result
