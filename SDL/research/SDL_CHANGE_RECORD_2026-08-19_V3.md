# SDL Change Record — 2026-08-19 — Early Prediction Research v3

STATUS: RESEARCH ONLY / PRODUCTION NOT MODIFIED

Change:
- Reframed the research objective from >22% -> 100% to >22% -> 40/45/50%.
- 40–50% is the practical intraday target zone.
- 100% is secondary historical context.
- Preserved strict point-in-time feature capture.
- No evidence score or probability has been introduced.
- No dashboard or production engine has been changed.

Reason:
The earlier 22% -> 100% metric answered the wrong business question. The system must identify candidates early enough to capture the practical 40–50% move.

Next decision gate:
Use factor_target_effects.csv and descriptive_target_effects.csv to determine which factors available at the first >22% observation actually improve 40/45/50% continuation.
