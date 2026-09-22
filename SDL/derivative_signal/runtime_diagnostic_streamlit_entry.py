from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = Path.cwd()

# The V1 diagnostic file is expected to have been copied to the project root.
v1 = PROJECT / "run_runtime_diagnostic_v1.py"
if not v1.exists():
    raise FileNotFoundError(
        "run_runtime_diagnostic_v1.py was not found in the project root. "
        "Copy the V1 diagnostic file here before running V2."
    )

sys.path.insert(0, str(PROJECT))
import run_runtime_diagnostic_v1 as diagnostic

diagnostic.main()
