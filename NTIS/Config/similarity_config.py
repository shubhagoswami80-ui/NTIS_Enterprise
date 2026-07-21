"""
=========================================================
NTIS Historical Similarity Engine
Module  : similarity_config.py
Version : 1.0.0
Release : R1

Purpose:
    Central configuration for the Historical Similarity
    Engine.

=========================================================
"""

# Number of historical matches to evaluate
TOP_MATCHES = 10

# Minimum similarity percentage required
MIN_SIMILARITY = 60.0

# Similarity classification thresholds
EXCELLENT_MATCH = 90.0
STRONG_MATCH = 80.0
GOOD_MATCH = 70.0
MODERATE_MATCH = 60.0

# Feature weights (must total 1.00)
FEATURE_WEIGHTS = {
    "PATTERN": 0.30,
    "SCORE": 0.20,
    "PROBABILITY": 0.15,
    "PRICE_OI_VOLUME": 0.20,
    "PCR": 0.10,
    "IVR_IVP": 0.05,
}
