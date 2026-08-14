# NTIS SDL — Derivative Directional Signal Project v0.1

Status: EXECUTION STARTED — design frozen before logic tuning
Date: 2026-08-14

## Boundary
- Separate from Straddle Breakout logic.
- Existing SDL source/data pipeline is READ ONLY.
- Existing SDL dashboard is reused.
- New dashboard area/tab is decision-oriented.
- Manual Process Latest Data button drives refresh.
- Current and previous accepted snapshots are sufficient live state.
- No P&L, order execution, SL/target, or broker integration in v0.1.
- Historical replay uses the same signal functions as live processing.

## Decision flow
1. Read latest accepted source data.
2. Compare with previous accepted snapshot.
3. Detect OHLC range events.
4. Classify Futures OI + price positioning.
5. Evaluate PE/CE OI and PE-CE structure.
6. Evaluate support/resistance location when available.
7. Add participation/volatility context when available.
8. Produce Direction + Evidence + State.
9. Refresh the Decision Signals tab.

## State
Persist only the minimum required for the next decision:
- previous accepted snapshot reference/state
- current signal view
- processing timestamp/version
No full duplicate source snapshots.

## Future-ready
Signal records retain timestamp, symbol, direction, state and reference price so a later P&L/outcome layer can be added without redesign.

## Explicitly excluded
- Any change to existing Straddle Breakout / 50% / 100% logic.
- New upstream data-generation logic.
- Arbitrary probability weights.
- Automatic BUY/SELL execution.
