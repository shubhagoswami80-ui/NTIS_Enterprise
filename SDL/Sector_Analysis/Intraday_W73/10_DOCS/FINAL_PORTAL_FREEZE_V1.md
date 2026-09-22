# NTIS Intraday W73 — Final Portal Freeze v1

The W73 portal is frozen as an operational, fail-closed portal.

This freeze does not claim that the current Daywise source proves the authoritative historical V8 ORB semantics.

## Frozen
- Exact V8 vocabulary and W73-A/W73-B unchanged.
- Missing values never become zero.
- Generic Daywise OI is not relabelled as futures OI.
- `reached_0_5x` remains a historical target only.
- Live decisions require exact V8 inputs; incomplete inputs remain `NOT_READY`.
- No strategy tuning from the September 18 diagnostic.
- No existing SDL production/dashboard files are modified by this bundle.
- Historical replay remains deferred until an authoritative opening ORB source is available.

## Final diagnostic gate
61 files, 219 symbols, 12,921 rows; first source timestamp `2026-09-18T09:18:09`; source does not cover 09:15.
ORB diagnostic counts: UP 97, DOWN 57, NO_BREAK 22, BOTH 43; 197 symbols showed a diagnostic breakout.

Because opening-window evidence is not proven, the portal must remain fail-closed rather than substitute a relaxed ORB definition.

## Re-entry requirement
A future source integration must separately prove opening-window coverage, causal High/Low, subsequent Close breakout, first-break direction, PIT consistency, and compatibility with frozen V8 semantics.
