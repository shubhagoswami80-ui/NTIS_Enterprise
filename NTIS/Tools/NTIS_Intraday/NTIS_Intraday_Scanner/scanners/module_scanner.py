from pathlib import Path
import ast

def scan_modules(root):
    result=[]
    for f in Path(root).rglob("*.py"):
        try:
            tree=ast.parse(f.read_text(encoding="utf-8",errors="ignore"))
            result.append({
                "file":str(f),
                "functions":[n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)],
                "classes":[n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]
            })
        except:
            pass
    return result
