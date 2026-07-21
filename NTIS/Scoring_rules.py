"""
=========================================================
NTIS Scoring Rules
Version : 1.0

Purpose:
    Define trading intelligence rules for NSE stocks.

Input:
    Market Master Data fields

Output:
    Individual score components

Scoring Areas:
    1. Price + OI Relationship
    2. Support / Resistance OI
    3. Volume + OI Momentum
    4. IV / PCR (Future Enhancement)

=========================================================
"""


# =====================================================
# PRICE + OI SCORING RULES
# =====================================================

def price_oi_score(row):
    """
    Analyze Price Change and OI Change relationship

    Returns:
        Score
        Reason
    """

    price = row.get("Price Chg %", 0)
    oi = row.get("OI Chg %", 0)

    score = 0
    reason = ""


    # Long Buildup
    if price > 0 and oi > 0:
        score = 5
        reason = "Long Buildup"


    # Short Buildup
    elif price < 0 and oi > 0:
        score = -5
        reason = "Short Buildup"


    # Short Covering
    elif price > 0 and oi < 0:
        score = 3
        reason = "Short Covering"


    # Long Unwinding
    elif price < 0 and oi < 0:
        score = -3
        reason = "Long Unwinding"


    return score, reason



# =====================================================
# SUPPORT / RESISTANCE SCORING RULES
# =====================================================

def support_resistance_score(row):
    """
    Analyze Support and Resistance OI strength

    Expected fields:
        Support Strength
        Resistance Strength
    """

    score = 0
    reason = ""


    support = row.get("Support Strength", "")
    resistance = row.get("Resistance Strength", "")


    if support == "Strong":
        score += 4
        reason += "Strong Support; "


    elif support == "Weak":
        score += 2
        reason += "Weak Support; "


    if resistance == "Strong":
        score -= 4
        reason += "Strong Resistance; "


    elif resistance == "Weak":
        score -= 2
        reason += "Weak Resistance; "


    return score, reason



# =====================================================
# VOLUME + OI MOMENTUM RULES
# =====================================================

def volume_oi_score(row):
    """
    Detect volume and OI breakout

    Expected fields:

        Volume Spike
        OI Spike
    """

    score = 0
    reason = ""


    volume = row.get("Volume Spike", False)
    oi_spike = row.get("OI Spike", False)


    if volume:
        score += 3
        reason += "Volume Spike; "


    if oi_spike:
        score += 3
        reason += "OI Spike; "


    return score, reason



# =====================================================
# PCR / IV FUTURE PLACEHOLDER
# =====================================================

def option_metrics_score(row):
    """
    Future Enhancement

    Will include:

    - PCR Change
    - ATM Straddle
    - IV Change
    - IV/HV Ratio

    """

    score = 0
    reason = ""


    # Reserved for future development

    return score, reason



# =====================================================
# FINAL SCORE COMBINATION
# =====================================================

def calculate_total_score(row):

    total_score = 0

    reasons = []


    # Price OI
    score, reason = price_oi_score(row)
    total_score += score

    if reason:
        reasons.append(reason)



    # Support Resistance
    score, reason = support_resistance_score(row)
    total_score += score

    if reason:
        reasons.append(reason)



    # Volume OI
    score, reason = volume_oi_score(row)
    total_score += score

    if reason:
        reasons.append(reason)



    # Option Metrics
    score, reason = option_metrics_score(row)
    total_score += score

    if reason:
        reasons.append(reason)



    return {
        "Score": total_score,
        "Reason": " | ".join(reasons)
    }



# =====================================================
# SIGNAL CLASSIFICATION
# =====================================================

def get_signal(score):

    if score >= 10:
        return "HIGH CONVICTION BUY"


    elif score >= 5:
        return "BUY WATCHLIST"


    elif score <= -10:
        return "HIGH CONVICTION SHORT"


    elif score <= -5:
        return "SELL WATCHLIST"


    else:
        return "NEUTRAL"