# W73 Semantic Parity Implementation Gate

The dashboard and single-entry integration are independent of strategy promotion.

The raw-to-V8 bridge currently remains provisional.

Before any live W73-A/B alert is promoted, the implementation must prove
exact parity with the frozen V8 semantics used to establish the 72.093%
historical baseline.

Required proof:
1. Exact V8 feature vocabulary.
2. Exact bucket thresholds.
3. Exact ORB and maturity semantics.
4. Exact direction/build-up mapping.
5. Exact persistence/agreement rules.
6. Missing values never converted to zero.
7. Point-in-time replay contains no future observations.
8. W73-A and W73-B remain separate.

The dashboard may display provisional/system state, but must not silently
present provisional calculations as validated trading signals.
