"""
=========================================================
NTIS Trade Validation Engine
Version : 1.0

Purpose:
    Convert Probability Engine output into
    actionable trade candidates.

Inputs:
    1. tis_short_probability.csv
    2. Support OI Report
    3. Resistance OI Report

Outputs:
    tis_trade_candidates.csv

=========================================================
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import glob


# =====================================================
# Paths
# =====================================================

BASE_DIR = Path("E:/NSE_Daily_Analysis")

OUTPUT_DIR = BASE_DIR / "Output"

NTIS_DIR = BASE_DIR / "NTIS"

MONTH_DATA = (
    BASE_DIR
    / "2026"
    / "July"
)


PROBABILITY_FILE = (
    OUTPUT_DIR
    / "ntis_short_probability.csv"
)


FINAL_OUTPUT = (
    OUTPUT_DIR
    / "ntis_trade_candidates.csv"
)


# =====================================================
# Utility Functions
# =====================================================

def find_latest_file(folder):

    files = glob.glob(
        str(folder / "*.xlsx")
    )

    if not files:
        raise FileNotFoundError(
            f"No Excel file found in {folder}"
        )

    return max(
        files,
        key=lambda x: Path(x).stat().st_mtime
    )


def calculate_risk(
        support_distance,
        resistance_distance
):

    if resistance_distance <= 3:
        return "HIGH"

    if support_distance <= 3:
        return "LOW"

    return "MEDIUM"


def calculate_stop_loss(
        entry,
        support
):

    if support > 0:

        sl = support * 0.995

        return round(sl, 2)

    return round(
        entry * 0.97,
        2
    )


def calculate_target(
        resistance
):

    if resistance > 0:

        return round(
            resistance,
            2
        )

    return None



# =====================================================
# Load Probability Data
# =====================================================

print("=" * 70)
print("NTIS TRADE VALIDATION ENGINE")
print("=" * 70)


print("\nLoading Probability Data...")


prob_df = pd.read_csv(
    PROBABILITY_FILE
)


print(
    "Probability Stocks:",
    len(prob_df)
)


# =====================================================
# Load Support Data
# =====================================================

support_folder = (
    MONTH_DATA
    /
    "03_Support_OI"
)


support_file = find_latest_file(
    support_folder
)


print(
    "\nSupport File:",
    support_file
)


support_df = pd.read_excel(
    support_file
)


support_df = support_df.rename(
    columns={
        "Strike": "Support",
        "Dist. From Strike %":
        "Support Distance %"
    }
)


support_df = support_df[
    [
        "Symbol",
        "Support",
        "Support Distance %",
        "PCR",
        "Fut Buildup"
    ]
]


# =====================================================
# Load Resistance Data
# =====================================================

resistance_folder = (
    MONTH_DATA
    /
    "04_Resistance_OI"
)


resistance_file = find_latest_file(
    resistance_folder
)


print(
    "Resistance File:",
    resistance_file
)


resistance_df = pd.read_excel(
    resistance_file
)


resistance_df = resistance_df.rename(
    columns={
        "Strike": "Resistance",
        "Dist. From Strike %":
        "Resistance Distance %"
    }
)


resistance_df = resistance_df[
    [
        "Symbol",
        "Resistance",
        "Resistance Distance %"
    ]
]


# =====================================================
# Merge Data
# =====================================================

df = prob_df.merge(
    support_df,
    on="Symbol",
    how="left"
)


df = df.merge(
    resistance_df,
    on="Symbol",
    how="left"
)


# =====================================================
# Validation Logic
# =====================================================

final_score = []


signals = []


risks = []

stop_losses = []

targets = []

reasons = []


for _, row in df.iterrows():

    score = 0

    reason = []


    # Probability

    probability = row[
        "BUY Probability %"
    ]


    if probability >= 85:

        score += 30
        reason.append(
            "High Probability"
        )


    elif probability >= 70:

        score += 20
        reason.append(
            "Good Probability"
        )


    # Pattern

    pattern = str(
        row["Pattern"]
    )


    if (
        "Long" in pattern
        or
        "Covering" in pattern
    ):

        score += 20
        reason.append(
            "Bullish Pattern"
        )


    # Support

    support_dist = row.get(
        "Support Distance %",
        99
    )


    if pd.notna(support_dist):

        if support_dist <= 3:

            score += 15
            reason.append(
                "Near Support"
            )


    # Resistance

    resistance_dist = row.get(
        "Resistance Distance %",
        99
    )


    if pd.notna(resistance_dist):

        if resistance_dist < 3:

            score -= 15
            reason.append(
                "Near Resistance"
            )


    # PCR

    pcr = row.get(
        "PCR",
        0
    )


    if pd.notna(pcr):

        if pcr > 1:

            score += 10
            reason.append(
                "Positive PCR"
            )


    # Risk

    risk = calculate_risk(
        support_dist,
        resistance_dist
    )


    risks.append(
        risk
    )


    # Trade

    if score >= 55:

        signals.append(
            "STRONG BUY"
        )

    elif score >= 40:

        signals.append(
            "BUY"
        )

    else:

        signals.append(
            "WAIT"
        )


    final_score.append(
        score
    )


    entry = row[
        "Entry Close"
    ]


    stop_losses.append(
        calculate_stop_loss(
            entry,
            row.get(
                "Support",
                0
            )
        )
    )


    targets.append(
        calculate_target(
            row.get(
                "Resistance",
                0
            )
        )
    )


    reasons.append(
        ", ".join(reason)
    )



# =====================================================
# Final Output
# =====================================================

df["Validation Score"] = final_score

df["Risk"] = risks

df["Stop Loss"] = stop_losses

df["Target"] = targets

df["Final Signal"] = signals

df["Reason"] = reasons


df = df.sort_values(
    by="Validation Score",
    ascending=False
)


if "Rank" in df.columns:
        df["Rank"] = range(1, len(df) + 1)
    
else:
        df.insert(
        0,
        "Rank",
        range(
            1,
            len(df)+1
    )
)


# =====================================================
# Final Output
# =====================================================

output_columns = [

    "Rank",
    "Symbol",
    "Pattern",
    "NTIS Score",
    "BUY Probability %",
    "Confidence",
    "Entry Close",

    "Support",
    "Resistance",

    "Risk",
    "Stop Loss",
    "Target",

    "Validation Score",
    "Final Signal",
    "Reason"
]


for col in [
    "Support Distance %",
    "Resistance Distance %",
    "PCR",
    "PCR_x",
    "PCR_y",
    "Fut Buildup"
]:

    if col in df.columns:
        output_columns.insert(
            output_columns.index("Risk"),
            col
        )


df[
    output_columns
].to_csv(
    FINAL_OUTPUT,
    index=False
)


print("\nCompleted Successfully")

print(
    "\nOutput:",
    FINAL_OUTPUT
)


print("\nTOP TRADE CANDIDATES")
print("-"*70)

print(
    df[
        output_columns
    ].head(20)
)
