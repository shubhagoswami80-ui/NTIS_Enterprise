# SDL Phase-1 Data Contract v1.2

- `Open` = today's fixed stock opening price / daily ATM reference.
- `High` = high reached so far.
- `Low` = low reached so far.
- `Close` = latest/current price in the supplied snapshot.
- `ATM Straddle %` = current straddle percentage.

Derived:
- `current_straddle_premium = Open × ATM Straddle % / 100`
- `base_straddle_premium = first accepted daily Open × first accepted daily ATM Straddle % / 100`
- `breakout_level = base_straddle_premium × 1.20`
- `valid_breakout = current_straddle_premium > breakout_level`

The daily Open remains the fixed reference across snapshots for the same trading date.
