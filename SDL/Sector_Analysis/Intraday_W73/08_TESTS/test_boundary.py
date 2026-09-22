from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "sector_data_loader", "sector_worker", "sector_page",
    "sector_rotation_engine", "sdl_decision_centre_preview",
    "prediction_engine", "source_loader", "storage"
}

def test_no_old_runtime_imports():
    violations = []
    for p in ROOT.rglob("*.py"):
        if "08_TESTS" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(name == x or name.startswith(x + ".") for x in FORBIDDEN):
                    violations.append((str(p.relative_to(ROOT)), name))
    assert not violations, violations
