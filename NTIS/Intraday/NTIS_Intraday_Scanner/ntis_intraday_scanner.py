from pathlib import Path
import json
from config.scanner_config import CODE_ROOT, DATA_ROOT
from scanners.module_scanner import scan_modules
from scanners.dependency_scanner import scan_dependencies
from scanners.dataflow_scanner import scan_dataflow
from scanners.intelligence_scanner import scan_intelligence

OUTPUT = Path(__file__).parent / "output"

def run():
    OUTPUT.mkdir(exist_ok=True)

    result = {
        "code_root": CODE_ROOT,
        "data_root": DATA_ROOT,
        "folder_architecture": {
            "code": scan_modules(CODE_ROOT),
            "data": scan_dataflow(DATA_ROOT)
        },
        "dependencies": scan_dependencies(CODE_ROOT),
        "intelligence": scan_intelligence(CODE_ROOT)
        + scan_intelligence(DATA_ROOT)
    }

    (OUTPUT / "architecture_map.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    return result

if __name__ == "__main__":
    run()
    print("NTIS Dual Root Architecture Scan Completed")
