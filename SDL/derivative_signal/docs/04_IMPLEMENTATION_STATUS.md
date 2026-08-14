# Implementation Status

## Started
- Project boundary and architecture frozen.
- Separate `derivative_signal` subfolder selected.
- Existing SDL pipeline remains read-only.
- Live refresh model defined around the existing manual Process Latest Data action.
- Same signal functions are intended for live and replay.
- Minimal runtime state defined.
- Decision-oriented dashboard requirement defined.

## Next integration gate
The local SDL root is the authoritative implementation target:
`E:\NSE_Daily_Analysis\SDL`

Before modifying `app.py` or `pipeline.py`, inspect the current local files and integrate only the minimum imports/calls required.

## Validation fixtures
- BHARTIARTL: use consecutive snapshots to validate previous-high break/hold plus evolving OI/PE-CE evidence.
- JUBLFOOD: validate bullish evidence does not become actionable when resistance/location evidence is unavailable.

## No logic tuning yet
No arbitrary score, threshold, probability or P&L rule has been added.
