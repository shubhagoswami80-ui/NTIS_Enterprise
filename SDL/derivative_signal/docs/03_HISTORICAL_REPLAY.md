# Historical Replay

The replay module provides a lightweight validation path.

Purpose:
- feed a chronological sequence of saved source workbooks
- reconstruct current/previous symbol state
- calculate OHLC transition evidence
- observe how the decision state changes over time

This is validation infrastructure, not a P&L engine.

No trading orders are generated.
No historical data is rewritten.
