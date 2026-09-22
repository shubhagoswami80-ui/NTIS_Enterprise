NTIS Intraday W73 — FINAL DEPLOYMENT BUNDLE v1

This bundle is the consolidated deployment source of truth for the frozen W73 portal.

Final state:
- Portal operational/frozen.
- Exact V8 strategy unchanged.
- W73-A/W73-B unchanged.
- Fail-closed NOT_READY when exact V8 inputs are incomplete.
- Exact historical ORB source is NOT proven from the current Daywise source.
- No production SDL changes are included.
- Raw external source remains read-only.

Precedence used while consolidating:
1. Data foundation
2. Exact V8 corrected engine
3. Live decision integration
4. Safe PID launch/stop
5. Final freeze documentation

The current Daywise source starts at 09:18:09 on the validated 2026-09-18 session and therefore does not prove the required opening ORB window. This bundle deliberately does not weaken V8 semantics to compensate.
