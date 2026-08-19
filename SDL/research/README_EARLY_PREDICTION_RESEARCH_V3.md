# SDL Early Prediction Research v3

Research-only enhancement. Production SDL is not changed.

## Objective
Identify intraday candidates EARLY enough to pursue a practical 40–50% straddle target.

The research trigger is the first observation where the frozen opening-reference straddle movement exceeds 22%.

### Primary outcomes
- 40% reached
- 45% reached
- 50% reached

### Secondary outcome
- 100% reached, retained only for historical context.

## Point-in-time integrity
Features are taken from the first >22% observation only.
Later snapshots are used only to determine whether a target was subsequently reached.

## Outputs
`data/output/early_prediction_research/`
- `first_22_point_in_time.csv`
- `research_summary.csv`
- `descriptive_target_effects.csv`
- `factor_target_effects.csv`

No score, probability, or production trade signal is generated.

## Run
From `E:\NSE_Daily_Analysis\SDL`:

```powershell
python research\early_prediction_research.py 2026-08-12 2026-08-13 2026-08-14 2026-08-19
```
