# Live Evidence Source Alignment — V1

## Purpose
Fix the LIVE evidence bridge so PIT Differential / EOD Unusual can use the **already-persisted historical replay cache** rather than only the current trading day's logical snapshots.

## What changes
- Reads prior `YYYY-MM-DD.pkl.gz` replay artifacts already present under `data/output/state/replay_cache`.
- Uses only dates strictly earlier than the LIVE trading date.
- Uses only `logical::` point-in-time frames; physical aliases are ignored.
- Adds the cache day's `trading_date` when a cached frame does not already carry it.
- Combines prior cached observations with the current day's already-processed logical frames.
- Does **not** run replay, rebuild source files, change checkpoints, or alter SDL/ranking/selection.
- EOD Unusual consumes the resulting PIT evidence through the existing validated V5/V6 engines.
- Historical Outcome remains governed by its strict forward-observation rule; it is not fabricated for a current LIVE event.
- PDNA remains evidence-only and is unchanged until its authoritative runtime source is connected.
- Alerts continue to use the existing alert store/rules; no rule is invented.

## Deployment
Copy the bundle into:
`E:\NSE_Daily_Analysis\SDL\derivative_signal`

Run:
`python .\deploy_live_evidence_source_alignment_v1.py`

Then compile/test:
`python -m compileall .\dashboard.py .\dashboard_evidence_bridge.py`
`pytest .\tests\test_live_historical_cache_loader.py -q`

No Git writes are performed.

## Safety boundary
SDL remains the decision owner. `selection_gate=False`. This is an additive evidence-source fix only.
