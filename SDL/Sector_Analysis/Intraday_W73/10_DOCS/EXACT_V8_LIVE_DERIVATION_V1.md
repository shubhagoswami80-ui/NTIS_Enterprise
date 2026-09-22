# W73 Exact V8 Live Derivation v1

## Objective

Move W73 from a structural V8 contract to a **point-in-time exact-V8 derivation layer**.

The implementation follows the authoritative GitHub source lineage:

- `SDL/Sector_Analysis/maturity_conditional_pattern_discovery_v8.py`
- `SDL/Sector_Analysis/data_strength_combination_study.py`
- `SDL/Sector_Analysis/smart_replay_strategy_study.py`

The preserved W73 `v8_feature_engine.py` remains the validation/matching contract.

## What this bundle does

1. Reads W73 PIT observations only.
2. Applies the authoritative canonical field-role mapping.
3. Preserves missing values.
4. Builds the price stream from complete OHLC observations.
5. Builds the ORB at the requested window.
6. Uses only evidence available at the maturity cutoff.
7. Reproduces the exact V8 `build_features()` semantics.
8. Reproduces the exact core/magnitude banding semantics.
9. Derives the pre-maturity trajectory without future leakage.
10. Evaluates W73-A and W73-B only when the complete exact vector exists.

## Important live-source limitation

The primary Daywise workbook is an OPTIONS-family source in the authoritative
canonical mapping. Therefore its generic `OI Chg` is **not silently relabelled
as futures OI**. If the separate FUTURES-family evidence required by the
authoritative mapping is absent, the exact V8 vector remains `NOT_READY`.

This is intentional. It prevents a visually complete but semantically false
BUY/SELL signal.

## Maturity checkpoints

The exact V8 maturity cuts are:

- 09:30
- 09:45
- 10:00
- 10:15

## Target separation

`reached_0_5x` is historical outcome data and is never used as a live feature.

## Deployment

NEW FILE:

`02_FEATURE_ENGINE\w73_exact_v8_live_engine.py`

NEW TEST:

`08_TESTS\test_w73_exact_v8_live_engine.py`

Do not modify the raw source or existing production SDL dashboard.

## Status semantics

- `READY`: complete exact V8 vector + trajectory available.
- `NOT_READY`: one or more exact inputs are missing or ORB/trajectory cannot be established.

`NOT_READY` must never be converted into a trade signal.
