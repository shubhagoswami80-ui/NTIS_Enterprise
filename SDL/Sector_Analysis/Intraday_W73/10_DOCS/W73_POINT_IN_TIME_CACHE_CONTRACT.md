# W73 Point-in-Time Cache Contract v1

Purpose:
- Persist W73 source observations locally after read-only ingestion.
- Preserve source timestamp, trading date, source filename, symbol, and raw fields.
- Keep missing values missing.
- Keep the external source tree untouched.

Cache root:
`NTIS_W73_CACHE_ROOT`
Default:
`E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73\.cache\point_in_time`

Cache key:
`trading_date / HHMMSS / observations.jsonl`

This cache is an ingestion/cache layer, not a strategy calculation layer.
V8 semantics remain owned by `02_FEATURE_ENGINE`.
