"""
NTIS Dashboard - Table Styles
Production styling helpers for Streamlit Styler.
"""

GREEN="#d4edda"
RED="#f8d7da"
YELLOW="#fff3cd"
BLUE="#dbeafe"

def _num(v):
    try:
        return float(v)
    except Exception:
        return None

def probability_style(v):
    n=_num(v)
    if n is None: return ""
    if n>=80: return "background-color:%s;font-weight:bold;"%GREEN
    if n>=70: return "background-color:%s;"%YELLOW
    return ""

def score_style(v):
    n=_num(v)
    if n is None: return ""
    if n>=90: return "background-color:%s;font-weight:bold;"%GREEN
    if n>=75: return "background-color:%s;"%BLUE
    if n>=60: return "background-color:%s;"%YELLOW
    return ""

def bias_style(v):
    t=str(v).upper()
    if t=="BUY":
        return "background-color:%s;font-weight:bold;"%GREEN
    if t=="SELL":
        return "background-color:%s;font-weight:bold;"%RED
    return ""

def pattern_style(v):
    t=str(v).lower()
    if "long" in t or "bull" in t:
        return "background-color:%s;"%GREEN
    if "short" in t or "bear" in t:
        return "background-color:%s;"%RED
    return ""

def style_buy(df):
    sty=df.style
    if "Probability" in df.columns:
        sty=sty.map(probability_style,subset=["Probability"])
    if "NTIS Score" in df.columns:
        sty=sty.map(score_style,subset=["NTIS Score"])
    if "Pattern" in df.columns:
        sty=sty.map(pattern_style,subset=["Pattern"])
    return sty

def style_sell(df):
    return style_buy(df)

def style_rank(df):
    sty=df.style
    if "NTIS Score" in df.columns:
        sty=sty.map(score_style,subset=["NTIS Score"])
    if "Probability" in df.columns:
        sty=sty.map(probability_style,subset=["Probability"])
    if "Trade Bias" in df.columns:
        sty=sty.map(bias_style,subset=["Trade Bias"])
    if "Pattern" in df.columns:
        sty=sty.map(pattern_style,subset=["Pattern"])
    return sty

def style_support(df):
    return df.style

def style_pattern(df):
    sty=df.style
    if "Average Probability" in df.columns:
        sty=sty.map(probability_style,subset=["Average Probability"])
    if "Average NTIS Score" in df.columns:
        sty=sty.map(score_style,subset=["Average NTIS Score"])
    return sty
