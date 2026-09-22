# W73 Live Data Foundation — FINAL Phase 1

## Objective
Provide the live intraday dashboard and the point-in-time data foundation that replay, historical analysis, and alerts will consume later.

## Frozen boundary
Raw source is READ ONLY. The folder trading date is authoritative. The filename timestamp is authoritative for observation time.

## Pipeline
Raw XLSX -> exact timestamp ingestion -> append-only point-in-time cache -> latest-as-of service -> stock universe -> priority board -> dashboard :9005.

## Timestamp contract
`_observation_timestamp` is source data time. It is not the same as processing time, display time, or future alert emission time.

## Universe contract
The primary dashboard contains only eligible stocks. Eligibility is based on configured required-field completeness and optional explicit thresholds. The full raw universe remains available only for diagnostics/audit.

## Replay boundary
Replay must consume the frozen cache and universe decisions; it must not rescan raw XLSX to redefine the past.

## Freeze gate
All phase-1 tests pass; live source validation passes; timestamp integrity passes; dashboard displays real data; existing SDL production remains untouched.
