from pathlib import Path

def scan_dashboard(root):
    return [str(x) for x in Path(root).rglob("*dashboard*.py")]
