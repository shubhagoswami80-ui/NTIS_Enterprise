"""
NTIS-EOD File Function Mapper v2.0
Fast read-only engineering discovery tool.
"""

from pathlib import Path
import ast
import csv
from datetime import datetime

NTIS_ROOT = Path(r"E:/NSE_Daily_Analysis/NTIS")
OUTPUT = NTIS_ROOT / "tools" / "Architecture_Report"
OUTPUT.mkdir(parents=True, exist_ok=True)

IGNORE = {".git", ".venv", "__pycache__", "Architecture_Report", "intraday"}

def ignored(path):
    return any(x in path.parts for x in IGNORE)

def write_csv(name, headers, rows):
    with open(OUTPUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

def main():
    functions = []
    classes = []
    imports = []
    files = []

    for file in NTIS_ROOT.rglob("*.py"):
        if ignored(file):
            continue

        rel = str(file.relative_to(NTIS_ROOT))
        files.append([rel])

        try:
            tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append([rel, node.name, ast.get_docstring(node) or ""])

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append([rel, node.name, ast.get_docstring(node) or ""])

                elif isinstance(node, ast.Import):
                    for item in node.names:
                        imports.append([rel, item.name])

                elif isinstance(node, ast.ImportFrom):
                    imports.append([rel, node.module or ""])

        except Exception:
            pass

    write_csv("NTIS_File_Map.csv", ["File"], files)
    write_csv("NTIS_Function_Map.csv", ["File", "Function", "Description"], functions)
    write_csv("NTIS_Class_Map.csv", ["File", "Class", "Description"], classes)
    write_csv("NTIS_Module_Dependency_Map.csv", ["Source", "Import"], imports)

    print("Completed:", datetime.now())
    print("Output:", OUTPUT)

if __name__ == "__main__":
    main()
