"""Controlled one-shot launcher V1.2."""
from pathlib import Path
import runpy
B=Path(__file__).resolve().parent
print("PCR/OI Strategy Research V1.2")
runpy.run_path(str(B/"feature_layer_engine.py"),run_name="__main__")
runpy.run_path(str(B/"strategy_discovery_engine.py"),run_name="__main__")
print("COMPLETE")
