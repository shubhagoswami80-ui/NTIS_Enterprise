"""
NTIS-EOD Engine Contract Validator v1.0

Bundle 01 - Platform Stabilization

Purpose:
    Validate frozen NTIS pipeline interfaces.

Checks:
    - Required input/output files
    - Required columns
    - Pipeline readiness

Read-only:
    Does not modify engines or data.
"""

from pathlib import Path
import pandas as pd


BASE = Path(r"E:/NSE_Daily_Analysis")

OUTPUT = BASE / "NTIS" / "tools" / "Architecture_Report"


CONTRACTS = {

    "Scoring Engine": {
        "input": BASE / "Output" / "market_master.csv",
        "output": BASE / "Output" / "ntis_ranked_stocks.csv",
        "columns": ["Symbol", "NTIS Score", "Signal"]
    },

    "Pattern Engine": {
        "input": BASE / "Output" / "ntis_ranked_stocks.csv",
        "output": BASE / "Output" / "ntis_pattern_analysis.csv",
        "columns": ["Symbol", "Pattern"]
    },

    "Probability Engine": {
        "input": BASE / "Output" / "ntis_pattern_analysis.csv",
        "output": BASE / "Output" / "ntis_probability_analysis.csv",
        "columns": [
            "BUY Probability %",
            "SELL Probability %"
        ]
    },

    "Trade Validation": {
        "input": BASE / "Output" / "ntis_probability_analysis.csv",
        "output": BASE / "Output" / "ntis_trade_candidates.csv",
        "columns": [
            "Symbol",
            "Final Signal"
        ]
    }
}


def validate_file(path):

    return path.exists()


def validate_columns(path, columns):

    try:
        df = pd.read_csv(path)

        missing = [
            c for c in columns
            if c not in df.columns
        ]

        return missing

    except Exception as exc:
        return [str(exc)]


def main():

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    results = []

    for engine, contract in CONTRACTS.items():

        input_ok = validate_file(contract["input"])
        output_ok = validate_file(contract["output"])

        missing = []

        if output_ok:
            missing = validate_columns(
                contract["output"],
                contract["columns"]
            )

        results.append(
            {
                "Engine": engine,
                "Input Available": input_ok,
                "Output Available": output_ok,
                "Missing Columns": ",".join(missing) if missing else ""
            }
        )

    report = pd.DataFrame(results)

    report_file = (
        OUTPUT /
        "NTIS_Engine_Contract_Validation.csv"
    )

    report.to_csv(
        report_file,
        index=False
    )

    print("Validation completed")
    print(report_file)
    print(report)


if __name__ == "__main__":
    main()
