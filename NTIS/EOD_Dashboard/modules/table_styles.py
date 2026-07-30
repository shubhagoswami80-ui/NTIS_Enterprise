"""
NTIS Dashboard - Table Styles
Enterprise Version
"""

GREEN = "#d4edda"
RED = "#f8d7da"
YELLOW = "#fff3cd"
BLUE = "#dbeafe"


def _num(value):
    try:
        return float(value)
    except Exception:
        return None


def probability_style(value):
    n = _num(value)

    if n is None:
        return ""

    if n >= 85:
        return f"background-color:{GREEN};font-weight:bold;"

    if n >= 75:
        return f"background-color:{BLUE};"

    if n >= 65:
        return f"background-color:{YELLOW};"

    return ""


def score_style(value):
    n = _num(value)

    if n is None:
        return ""

    if n >= 90:
        return f"background-color:{GREEN};font-weight:bold;"

    if n >= 80:
        return f"background-color:{BLUE};"

    if n >= 70:
        return f"background-color:{YELLOW};"

    return ""


def bias_style(value):

    text = str(value).strip().upper()

    if text == "BUY":
        return f"background-color:{GREEN};font-weight:bold;"

    if text == "SELL":
        return f"background-color:{RED};font-weight:bold;"

    return ""


def confidence_style(value):

    text = str(value).strip().upper()

    if text == "HIGH":
        return f"background-color:{GREEN};"

    if text == "MEDIUM":
        return f"background-color:{YELLOW};"

    if text == "LOW":
        return f"background-color:{RED};"

    return ""


def pattern_style(value):

    text = str(value).lower()

    if "long" in text or "bull" in text:
        return f"background-color:{GREEN};"

    if "short" in text or "bear" in text:
        return f"background-color:{RED};"

    return ""


def style_buy(df):

    sty = df.style

    if "Probability" in df.columns:
        sty = sty.map(probability_style, subset=["Probability"])

    elif "BUY Probability %" in df.columns:
        sty = sty.map(probability_style, subset=["BUY Probability %"])

    if "NTIS Score" in df.columns:
        sty = sty.map(score_style, subset=["NTIS Score"])

    if "Confidence" in df.columns:
        sty = sty.map(confidence_style, subset=["Confidence"])

    if "Pattern" in df.columns:
        sty = sty.map(pattern_style, subset=["Pattern"])

    return sty


def style_sell(df):
    return style_buy(df)


def style_rank(df):

    sty = style_buy(df)

    for column in (
        "Trade Bias",
        "Final Signal",
        "Signal",
        "Validation Signal",
    ):

        if column in df.columns:
            sty = sty.map(bias_style, subset=[column])
            break

    return sty


def style_support(df):
    return df.style


def style_pattern(df):

    sty = df.style

    if "Average Probability" in df.columns:
        sty = sty.map(
            probability_style,
            subset=["Average Probability"],
        )

    if "Average NTIS Score" in df.columns:
        sty = sty.map(
            score_style,
            subset=["Average NTIS Score"],
        )

    return sty