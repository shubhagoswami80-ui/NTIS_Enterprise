# W73 Real-Source Runtime Validation v1

Purpose: exercise the installed W73 stack against the approved read-only Daywise XLSX source.

Flow:
RAW XLSX -> source adapter -> W73 PIT cache -> Exact V8 live decision service -> W73-A/B decision summary.

The external source is never modified. Only W73 cache/output paths are written.

Run from W73 root:
`python 08_TESTS\w73_real_source_runtime_validation.py September26 2026-09-18`

For a current trading day, replace the date with the actual W73 source day folder. If the folder does not exist, the validator fails rather than substituting another date.

Output: `07_OUTPUT\real_source_runtime_validation_v1.json`

This is runtime validation, not historical replay. Historical replay remains a later frozen phase after current-day logic is finalized.
