# SDL Phase-1 Implementation Note

## Frozen calculation

`Open` is today's stock opening price and remains fixed during the trading day.

`Current Straddle Premium = Today's Fixed Open × Current ATM Straddle % / 100`

The current `Close` is NOT used as the straddle strike/reference.

The first accepted snapshot establishes the day's base:
`Base = Today's Open × ATM Straddle % / 100`

The base is frozen for the day.

`Breakout Level = Base × 1.20`

Valid breakout:
`Current Straddle Premium > Breakout Level`

Exactly 20% is not a breakout.

## Phase-1 limitation

The first supplied snapshot is the first observed base unless a separate opening straddle observation is supplied. SDL does not invent a previous-day ATM or reconstruct CE/PE premiums.
