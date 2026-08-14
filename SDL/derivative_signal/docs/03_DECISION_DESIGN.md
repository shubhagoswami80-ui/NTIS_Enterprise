# Decision Design v0.1

## Price structure
Compare the current accepted snapshot with the previous accepted snapshot.

Bullish range breakout:
- current High > previous High
- current Close > previous High

Bearish range breakdown:
- current Low < previous Low
- current Close < previous Low

Other states:
- RANGE
- BREAKOUT_REJECTED
- BREAKDOWN_REJECTED
- NO_CHANGE

## Futures positioning
Price/OI classification only:
- price up + OI up = Long Buildup
- price down + OI up = Short Buildup
- price up + OI down = Short Covering
- price down + OI down = Long Unwinding

This is evidence, not an automatic trade.

## Options structure
Use PE OI, CE OI and PE-CE OI as evidence.
Do not hard-code numeric thresholds until historical evidence exists.

## Location gate
If a nearby resistance is known for a bullish setup, do not mark it actionable merely because derivatives are aligned.
If a nearby support is known for a bearish setup, apply the same rule.
Missing location is reported as UNKNOWN, not guessed.

## Decision states
- WATCH
- DEVELOPING
- CONFIRMED
- NO TRADE
- INSUFFICIENT DATA

ACTIONABLE remains deferred until historical validation establishes evidence-backed criteria.

## Dashboard principle
Show the reason for the state, not raw columns alone.
