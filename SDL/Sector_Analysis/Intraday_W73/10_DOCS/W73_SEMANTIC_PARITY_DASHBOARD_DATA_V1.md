# W73 Semantic Parity + Dashboard Data Layer v1

This bundle advances two things together:

1. A structural forensic parity check against the authoritative local V8
   matrix and copied V8 research source.
2. A frozen dashboard data contract for the standalone W73 dashboard.

## Critical distinction

Structural parity is NOT semantic parity.

The parity inspector therefore cannot promote a signal. It only identifies
whether the expected V8 feature vocabulary is represented in the authoritative
matrix/source.

Exact semantic parity still requires validating:
- thresholds;
- direction/build-up mapping;
- ORB logic;
- maturity logic;
- persistence;
- evidence/agreement;
- bucket boundaries;
- missing-value handling;
- point-in-time behavior.

## Dashboard

Port: `9005`

Public integration function:
`render_intraday_w73_page`

Variants remain independent:
- W73-A
- W73-B

No OR-union is permitted.
