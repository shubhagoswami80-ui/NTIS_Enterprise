# Implementation Status v0.2

All new files are inside `SDL/derivative_signal/`.

`SDL/app.py` is deliberately NOT included and must not be replaced.

Implemented:
- separate dashboard entry point
- dashboard-controlled date/source
- manual processing
- OHLC transition evidence
- primary OI evidence
- PE-CE evidence
- decision states
- explanation
- minimal previous-snapshot state
- replay module

Not implemented:
- explicit Futures OI until source/header is verified
- secondary Support/Resistance/IV/Volume dependencies
- P&L
- automatic trading
- arbitrary scoring/probability
- changes to Straddle Breakout logic
