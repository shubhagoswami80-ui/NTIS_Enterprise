# W73 ORB Source Capability Audit v1

Purpose: diagnose whether the current Daywise XLSX source can reproduce the authoritative V8/Smart Replay ORB semantics.

This bundle is diagnostic only. It does not modify strategy logic, V8 semantics, the dashboard, or the source files.

The audit samples actual source snapshots and compares High/Low/Close/Price Chg/Price Chg % over time for selected symbols.

Interpretation:
- Changing Close proves a point-in-time price series exists, but does not prove candle semantics.
- Repeated/monotonic High or Low behavior can indicate cumulative/session fields and must be inspected rather than assumed.
- Authoritative ORB requires an initial window high/low and a later close breakout.

Run from the W73 root:
`python 08_TESTS\..\10_DOCS\orb_source_capability_audit_v1.py September26 2026-09-18 --symbol RELIANCE --symbol HDFCBANK`

No existing production/SDL files are modified.
