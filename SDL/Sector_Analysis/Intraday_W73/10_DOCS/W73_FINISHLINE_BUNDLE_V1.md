# W73 Maximum Finish-Line Bundle v1

## Objective

Accelerate the remaining implementation without changing the existing SDL
dashboard or the external raw-data source.

## Included layers

1. Raw source → provisional V8 state bridge.
2. Point-in-time chronological replay.
3. Replay manifest.
4. Alert/readiness gate.
5. Leakage tests.
6. Structural integration tests.

## Critical semantic gate

`w73_raw_v8_bridge.py` deliberately labels its output
`DERIVED_PROVISIONAL`.

It must NOT be promoted to production strategy matching merely because the
shape is correct.

Promotion requires exact semantic parity with the frozen V8 research
semantics/matrix. Unknown or missing states remain missing and therefore
cannot match W73-A/B.

## Finish-line sequence

RAW XLSX
→ source adapter
→ point-in-time cache
→ canonical observation
→ provisional raw-to-state bridge
→ exact V8 semantic parity validation
→ W73-A/B matcher
→ historical replay
→ alert/readiness layer
→ dashboard integration

Existing SDL production remains untouched until final integration.
