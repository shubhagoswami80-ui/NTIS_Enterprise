"""
=========================================================
NTIS Historical Similarity Engine
Module  : similarity_config.py
Version : 1.0.1
Release : HMME-01

Purpose:
    Central configuration for Historical Similarity Engine
    with Candidate Selector settings.
=========================================================
"""

# Number of historical matches to evaluate
TOP_MATCHES = 10

# Minimum similarity percentage required
MIN_SIMILARITY = 60.0

EXCELLENT_MATCH = 90.0
STRONG_MATCH = 80.0
GOOD_MATCH = 70.0
MODERATE_MATCH = 60.0


FEATURE_WEIGHTS = {
    "PATTERN": 0.30,
    "SCORE": 0.20,
    "PROBABILITY": 0.15,
    "PRICE_OI_VOLUME": 0.20,
    "PCR": 0.10,
    "IVR_IVP": 0.05,
}


# =========================================================
# HMME-01 Candidate Selector Configuration
# =========================================================

CANDIDATE_SELECTOR_CONFIG = {

    # Allowed NTIS score difference
    "score_window": 10,

    # Match same historical pattern
    "require_pattern_match": True,

    # Match same BUY/SELL direction
    "require_trade_bias_match": True,

    # Reserved for future validation
    "minimum_candidates": 5,
}
