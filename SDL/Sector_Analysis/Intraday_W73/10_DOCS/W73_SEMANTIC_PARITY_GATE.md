# W73 Exact V8 Semantic Parity Gate

The historical W73 baseline is frozen at 72.093%.

The current raw source contains business measurements, while W73 matching
requires the V8 state vector. Therefore structural field presence is not
sufficient.

A promotion test must establish:

- exact feature names;
- exact categorical values;
- exact maturity handling;
- exact ORB handling;
- exact direction/build-up semantics;
- exact percentage buckets;
- exact agreement/persistence logic;
- missing != zero;
- no future interval leakage;
- W73-A and W73-B remain independent.

Until all are proven, a vector is marked `DERIVED_PROVISIONAL` and cannot
generate a strategy alert.
