# Current Git Integration Targets

Read-only Git baseline: `f052e8390f1da69fefdcf83956a6c19cc50d91ca` (`master`).

Current Git dashboard contains the embedded Retracement lifecycle and existing RSI/MTF display/evidence helpers. This bundle deliberately does not replace those implementations.

Integration target later:

1. Read the authoritative existing SDL result.
2. Read the existing Retracement lifecycle/evidence output.
3. Read the isolated RSI/MTF evidence output from Bundle V3.
4. Pass those outputs to `build_stock_state_evidence()`.
5. Render the resulting state as an additional evidence view only.

No Git write was performed for this bundle.
