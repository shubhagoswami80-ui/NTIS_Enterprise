# NTIS Intraday W73 — Live Decision Integration v1

## Purpose

Connect the validated W73 point-in-time cache to the Exact V8 live derivation engine and expose a real decision board on port 9005.

## Runtime chain

RAW XLSX → live ingestor → PIT cache → universe filter → Exact V8 live derivation → W73-A/W73-B variant state → QUALIFIED / WAIT / NOT_READY → dashboard.

## Safety properties

- Only observations at or before the maturity cutoff are admitted.
- The trading-date folder remains authoritative.
- Missing values are never converted to zero.
- Exact V8 remains fail-closed when required fields are missing.
- `reached_0_5x` is never consumed by the live engine.
- W73-A and W73-B remain separate variants; there is no OR-union promotion.
- The dashboard does not modify the raw source tree.

## Important live-source limitation

The current Daywise source may not contain a FUTURES-family observation. The Exact V8 engine therefore leaves futures fields missing instead of relabelling generic OI as futures OI. Such symbols remain `NOT_READY` until the required exact-V8 inputs are actually present.

This is intentional and is not a signal failure workaround.

## Dashboard semantics

- `QUALIFIED`: exact V8 vector is complete and one frozen W73 variant matches.
- `WAIT`: exact V8 vector is complete but neither frozen W73 variant matches.
- `NOT_READY`: exact V8 vector or trajectory is incomplete.

## Existing SDL production

No existing SDL production/dashboard file is modified by this bundle. Only W73 files are changed.
