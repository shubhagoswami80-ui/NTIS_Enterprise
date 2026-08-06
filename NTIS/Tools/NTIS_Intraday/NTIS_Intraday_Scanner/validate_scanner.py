from pathlib import Path
import sys

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"

required_files = [
    OUTPUT / "Intraday_engineering_metadata.json",
    OUTPUT / "Documentation" / "04_MODULE_DEPENDENCY_MAP.md",
    OUTPUT / "Documentation" / "16_MODULE_IMPLEMENTATION_REGISTRY.md",
    OUTPUT / "Documentation" / "17_RUNTIME_OUTPUT_REGISTRY.md",
    OUTPUT / "Documentation" / "18_INTELLIGENCE_DEPENDENCY_GRAPH.md",
    OUTPUT / "Documentation" / "21_MODULE_CALL_GRAPH.md",
    OUTPUT / "AI_Context" / "project_summary.json",
    OUTPUT / "AI_Context" / "module_registry.json",
    OUTPUT / "AI_Context" / "dependency_graph.json",
    OUTPUT / "AI_Context" / "runtime_registry.json",
    OUTPUT / "AI_Context" / "intelligence_index.json",
]

missing = []

for file in required_files:
    if not file.exists():
        missing.append(file)

print()
print("=" * 60)
print("NTIS_Intraday Scanner Validation")
print("=" * 60)

if missing:
    print("\nFAILED\n")
    print("Missing Files:\n")
    for f in missing:
        print(f" - {f}")
    sys.exit(1)

print("\nSUCCESS\n")
print("All engineering artifacts generated successfully.")
print()
print(f"Validated {len(required_files)} artifacts.")