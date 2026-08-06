from pathlib import Path
import json

from config.scanner_config import CODE_ROOT, DATA_ROOT

from scanners.module_scanner import scan_modules
from scanners.dependency_scanner import scan_dependencies
from scanners.dataflow_scanner import scan_dataflow
from scanners.intelligence_scanner import scan_intelligence

from generators.documentation_generator import DocumentationGenerator
from generators.ai_context_generator import AIContextGenerator


ROOT = Path(__file__).parent

OUTPUT = ROOT / "output"

ENGINEERING_METADATA = OUTPUT / "Intraday_engineering_metadata.json"

DOCUMENTATION_OUTPUT = OUTPUT / "Documentation"

AI_CONTEXT_OUTPUT = OUTPUT / "AI_Context"


def run():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    metadata = {

        "code_root": CODE_ROOT,

        "data_root": DATA_ROOT,

        "folder_architecture": {

            "code": scan_modules(CODE_ROOT),

            "data": scan_dataflow(DATA_ROOT)

        },

        "dependencies": scan_dependencies(CODE_ROOT),

        "intelligence":

            scan_intelligence(CODE_ROOT)

            +

            scan_intelligence(DATA_ROOT)

    }

    ENGINEERING_METADATA.write_text(

        json.dumps(

            metadata,

            indent=4,

            ensure_ascii=False

        ),

        encoding="utf-8"

    )

    DocumentationGenerator(

        ENGINEERING_METADATA,

        DOCUMENTATION_OUTPUT

    ).generate()

    AIContextGenerator(

        ENGINEERING_METADATA,

        AI_CONTEXT_OUTPUT

    ).generate()

    return metadata


if __name__ == "__main__":

    run()

    print()

    print("NTIS_Intraday Engineering Scan Completed")

    print(f"Engineering Metadata : {ENGINEERING_METADATA}")

    print(f"Documentation        : {DOCUMENTATION_OUTPUT}")

    print(f"AI Context           : {AI_CONTEXT_OUTPUT}")