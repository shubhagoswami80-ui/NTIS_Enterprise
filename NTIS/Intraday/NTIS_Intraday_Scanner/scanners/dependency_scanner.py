from pathlib import Path
import ast

def scan_dependencies(root):
    result=[]
    for f in Path(root).rglob("*.py"):
        try:
            tree=ast.parse(f.read_text(encoding="utf-8",errors="ignore"))
            imports=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):
                    imports.extend([x.name for x in n.names])
                elif isinstance(n,ast.ImportFrom):
                    imports.append(n.module)
            result.append({"file":str(f),"imports":imports})
        except:
            pass
    return result
