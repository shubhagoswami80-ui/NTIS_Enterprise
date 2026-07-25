
"""
NTIS V17 Dependency Impact Analyzer

Purpose:
Analyze V17 modules before cleanup.

Safety:
- No files moved
- No files deleted
- No imports changed
"""

from pathlib import Path
import ast


BASE = Path(__file__).parent


def extract_imports(file_path):

    imports = []

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    imports.append(item.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

    except Exception:
        pass

    return imports


def analyze():

    files = list(BASE.glob("*_v17.py"))

    module_map = {}

    for file in files:
        module_map[file.stem] = extract_imports(file)

    core_dependencies = []
    module_dependencies = []
    standalone = []
    migration = []

    all_modules = set(module_map.keys())

    for module, imports in module_map.items():

        name = module + ".py"

        if any(x in module.lower() for x in [
            "activation",
            "checkpoint",
            "validation",
            "shadow",
            "dry_run",
            "switch",
            "migration"
        ]):
            migration.append(name)
            continue

        referenced = False

        for other, other_imports in module_map.items():
            if other == module:
                continue

            if module in " ".join(other_imports):
                referenced = True
                break

        if referenced:
            module_dependencies.append(name)
        else:
            standalone.append(name)

        if "core" in module.lower():
            core_dependencies.append(name)

    output = BASE / "V17_Dependency_Report"
    output.mkdir(exist_ok=True)

    reports = {
        "CORE_DEPENDENCIES.txt": core_dependencies,
        "MODULE_DEPENDENCIES.txt": module_dependencies,
        "STANDALONE_CANDIDATES.txt": standalone,
        "MIGRATION_ARTIFACTS.txt": migration,
    }

    for filename, items in reports.items():
        (output / filename).write_text(
            "\n".join(sorted(items)),
            encoding="utf-8"
        )

    print("V17 DEPENDENCY IMPACT REPORT READY")

    for filename, items in reports.items():
        print(filename, len(items))


if __name__ == "__main__":
    analyze()
