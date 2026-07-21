"""
=========================================================
NTIS Historical Market Memory Engine Configuration
Module  : hmme_config.py
Version : 1.0.0
Release : HMME Foundation

Purpose:
    Central configuration for Historical Market Memory Engine.

Design:
    - No hard-coded learning rules
    - Supports Intraday and EOD learning
    - Performance conscious
    - Future calibration ready
=========================================================
"""


# =========================================================
# Candidate Selector Configuration
# =========================================================

CANDIDATE_SELECTOR_CONFIG = {

    # Allowed NTIS score difference
    "score_window": 10,

    # Match same market pattern
    "require_pattern_match": True,

    # Match same BUY/SELL direction
    "require_trade_bias_match": True,

    # Minimum useful candidate count
    "minimum_candidates": 5,
}


# =========================================================
# Outcome Filter Configuration
# =========================================================

OUTCOME_FILTER_CONFIG = {

    # Minimum meaningful movement
    "minimum_move_percent": 1.5,

    # Strong move classification
    "strong_move_percent": 2.0,

    # Future outcome horizon
    "lookahead_days": 1,

    # BUY/SELL direction aware filtering
    "direction_sensitive": True,
}


# =========================================================
# Intraday Historical Memory Configuration
# =========================================================

INTRADAY_MEMORY_CONFIG = {

    "enabled": True,

    "allowed_snapshots": [
        "09:45",
        "10:00",
        "10:15",
    ],

    # Same timestamp comparison only
    "same_time_comparison_only": True,
}


# =========================================================
# EOD Historical Memory Configuration
# =========================================================

EOD_MEMORY_CONFIG = {

    "enabled": True,

    # Next trading day evaluation
    "lookahead_days": 1,
}


# =========================================================
# Performance Configuration
# =========================================================

HMME_PERFORMANCE_CONFIG = {

    # Avoid huge similarity calculations
    "max_candidates_before_similarity": 2000,

    # Large file processing support
    "chunk_size": 50000,

    # Future optimization hook
    "enable_cache": True,
}


# =========================================================
# Learning Statistics Configuration
# =========================================================

LEARNING_STATISTICS_CONFIG = {

    "minimum_sample_size": 30,

    "confidence_levels": [
        60,
        70,
        80,
        90,
    ],
}
