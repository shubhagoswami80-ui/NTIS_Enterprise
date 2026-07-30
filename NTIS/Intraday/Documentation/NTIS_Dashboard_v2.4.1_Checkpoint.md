# NTIS Intraday Dashboard v2.4.1 Checkpoint

## Current Milestone

Dashboard v2.4.1 finalization.

## Frozen Decisions

-   Dashboard UI design approved.
-   No redesign.
-   Existing pipeline unchanged.
-   Streamlit runtime remains Port 8502.
-   Existing PowerShell launcher remains startup method.

## Dashboard Scope

Included: - Approved dashboard layout - Navigation structure - Market
summary cards - Top intraday opportunities - Inline filters: - Signal -
Confidence - Pattern - Trade detail panel - Historical intelligence
placeholders

Excluded: - Scoring engine changes - Pattern engine changes -
Probability engine changes - Trade validation changes - Replay logic
inside dashboard - Calibration changes

## Intelligence Direction

Decision output will evolve through:

Current Market Data + Historical Pattern Validation + Replay Outcomes +
Calibration

= Decision Confidence

## Next Phase

Historical Evidence Layer: 1. Historical pattern matching 2. Outcome
verification 3. Evidence strength calculation 4. Dashboard integration

Future: Replay Validation Engine followed by Probability Calibration.

## Deployment Rule

Before replacement: 1. Validate exact source. 2. Test. 3. Package
controlled bundle. 4. Deploy. 5. Update checkpoint.

## Resume Point

Continue from Dashboard v2.4.1 release validation.
