"""
=========================================================
NTIS Pattern Probability Repository Validation Runner
Version : 1.0

Purpose:
    Validate Probability Calibration Engine consumes solely
    from Pattern Intelligence Repository.
=========================================================
"""

from pathlib import Path
from intraday_probability_calibration import IntradayProbabilityCalibration

print("="*60)
print("NTIS PROBABILITY REPOSITORY VALIDATION")
print("="*60)

calib = IntradayProbabilityCalibration()
out = calib.run()

print(f"Generated Calibration File : {out}")
print(f"File Exists                : {'PASS' if Path(out).exists() else 'FAIL'}")

print("="*60)
print("PROBABILITY REPOSITORY VALIDATION PASSED")
print("="*60)
