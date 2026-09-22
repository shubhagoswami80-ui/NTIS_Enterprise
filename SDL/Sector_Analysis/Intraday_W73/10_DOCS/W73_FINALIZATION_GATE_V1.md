# NTIS Intraday W73 — Finalization Gate v1

## Purpose
Final controlled gate before declaring the W73 portal's exact live V8 signal path finalized.

## What it tests
- Reads the real Daywise source read-only.
- Loads all selected-day interval workbooks.
- Verifies chronological source coverage.
- Tests whether the source can reproduce a causal ORB-style breakout from High/Low/Close.
- Explicitly checks whether the source reaches the 09:15 market-open reference.
- Does not modify strategy/V8 semantics, dashboard code, or source files.

## Exactness rule
The historical authoritative ORB starts from the opening price stream and uses the first 15-minute high/low followed by a later Close breakout. A source beginning at 09:18 cannot, by itself, prove an exact 09:15–09:30 ORB.

Therefore:
- `EXACT_ORB_SOURCE_READY` requires source coverage at or before 09:15 and at least one causal breakout reconstruction.
- Otherwise the result is `EXACT_ORB_SOURCE_NOT_PROVEN` and the live V8 engine remains fail-closed (`NOT_READY`).

## Portal finalization policy
The portal/UI may be finalized as a production-safe read-only decision board only with `NOT_READY` shown honestly where exact V8 inputs are unavailable. It must not manufacture a Qualified/Wait signal from incomplete ORB/futures inputs.

## Run
From W73 root:
`python 08_TESTS\w73_finalization_gate.py September26 2026-09-18`

Output:
`07_OUTPUT\w73_finalization_gate_v1.json`

## Copy policy
All files in this bundle are NEW FILES. No existing W73 files are replaced by this gate bundle.
