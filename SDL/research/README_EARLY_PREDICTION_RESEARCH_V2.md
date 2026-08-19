# SDL Early Prediction Research v2 — Research Only

This is the corrected continuation of the SDL enhancement work.

## Baseline
Validated against the latest Git baseline commit:
`713c8344b373033c8cd24135ee820be681edd8c9`

The production dashboard and Phase-1 breakout logic are NOT changed.

## Why this exists
The rejected prior implementation incorrectly converted data availability into positive evidence and created tradeable decisions before the research was validated.

This version deliberately does NOT create:
- evidence scores
- probabilities
- tradeable labels
- automatic entry decisions

It creates the research evidence needed to determine whether those things are justified.

## Core rule
For each symbol/day:
- freeze the opening price and opening straddle from the first chronological Daywise snapshot;
- find the FIRST observation where absolute movement exceeds 22% of that frozen straddle;
- capture every available factor from that exact observation only;
- replay later observations to determine whether 100% was subsequently reached.

No later observation is allowed to influence the first-22% feature values.

## ORB
ORB is recorded descriptively.
It is only considered complete when the source sequence covers both 09:15 and 09:30.
If the source begins after 09:15, ORB is `PARTIAL` and is not treated as evidence.

## Futures OI
The script records a physical source-column mapping.
If futures OI columns do not exist, they remain unavailable.
The existing generic `OI Chg %` is NOT silently relabeled as futures OI.

## Run
From:
`E:\NSE_Daily_Analysis\SDL`

```powershell
python research\early_prediction_research.py 2026-08-12 2026-08-13 2026-08-14 2026-08-19
```

Expected output:
`data\output\early_prediction_research\`

## Outputs
- `first_22_point_in_time.csv` — one row per first >22% event with only point-in-time factors.
- `source_schema_map.csv` — physical source columns actually found.
- `descriptive_outcomes.csv` — simple continuation rates by direction/progress/ORB status.
- `research_summary.csv` — coverage and outcome counts.
- `snapshot_replay_source.csv` — research replay source, not a decision table.

## Acceptance criteria before any dashboard change
1. First >22% event is correct for each symbol/day.
2. Opening base is frozen from the first source snapshot.
3. No future leakage exists in point-in-time features.
4. Futures OI is physically verified.
5. ORB completeness is explicit.
6. Direction-specific effects can be measured.
7. Enough historical samples exist before any rule/probability is frozen.
