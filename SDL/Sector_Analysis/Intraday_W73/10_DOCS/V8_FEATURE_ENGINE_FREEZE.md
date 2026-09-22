# W73 V8 Feature Engine Freeze

Status: IMPLEMENTATION READY — exact-V8 semantic source still authoritative

## Scope

This bundle establishes the W73-owned feature-engine boundary.

It:
1. validates the exact V8 feature vocabulary;
2. preserves missing != zero;
3. derives only the frozen pre-maturity price trajectory fields;
4. matches W73-A and W73-B independently;
5. has no runtime dependency on legacy SDL modules.

## Required authoritative matrix

W73 must own a copy of:

`maturity_feature_matrix.csv`

Expected destination:

`E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73\00_BASELINE\maturity_feature_matrix.csv`

The matrix is required for audit/reproduction of exact V8 semantics. The engine
does not silently substitute reconstructed semantics when that matrix is absent.

## Baseline remains frozen

W73 baseline:
- maximum robust holdout: 72.093%
- n: 129
- dates: 5
- symbols: 45
- tied candidates: 2

No new OR-union rule is introduced.
