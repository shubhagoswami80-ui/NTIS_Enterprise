# W73 Live Dashboard Freeze Gate

PASS only when:
- real source ingestion works
- exact timestamps are preserved
- PIT cutoff excludes future files
- missing data remains missing
- filtered stock universe is visible
- dashboard uses real cache data
- refresh/freshness works
- port 9005 is stable
- safe PID lifecycle is active
- tests pass
- existing SDL production dashboard is untouched

After PASS, freeze the live data contract. Replay/historical work starts only after this gate.
