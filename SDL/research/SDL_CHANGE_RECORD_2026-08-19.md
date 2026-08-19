# SDL Change Record — 2026-08-19 — Early Prediction Research v2

## Status
Research-only. Production NOT modified.

## Authoritative baseline
Git commit: 713c8344b373033c8cd24135ee820be681edd8c9

## Rejected prior approach
The previous attempted implementation is rejected because it produced large numbers of 100/100 evidence decisions without validated factor directionality and did not establish a clean first->22% point-in-time research layer.

## Corrected implementation
Added only:
- `research/early_prediction_research.py`
- this README
- this change record

## Business logic
22% is an evaluation trigger.
Price movement is Gate 1, but it is not sufficient for a trade decision.
The research phase determines whether secondary factors actually add predictive value.

Secondary factors are captured at the first >22% observation:
- generic OI change
- CE OI change
- PE OI change
- PE-CE OI change
- PCR change
- IV change
- volume / volume change
- IVR / IVP / IV-HV fields when physically available
- futures OI fields only when physically present
- ORB status/alignment

No factor is rewarded for merely being populated.

## Validation case
HAL 2026-08-19 remains a useful control case:
it crossed the early movement region but did not demonstrate that all secondary evidence was aligned.

## Next step
Run the research over 12, 13, 14 and 19 August, inspect schema availability and continuation rates, then decide which factors—if any—justify a deterministic decision rule.
