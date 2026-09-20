# NTIS SDL — B3 Universal Alert + Chart Extension

## Deployment boundary
Copy this `alert_chart` directory to:
`E:\NSE_Daily_Analysis\SDL\extensions\alert_chart\`

Do not place these modules in the SDL root and do not modify the frozen decision engine, replay gates, Futures mapping, cache worker, or source workbooks as part of this deployment.

## Status
Isolated B3 development package. It is ready for controlled integration testing, but is **not yet integrated into or deployed to the production dashboard**.

## Scope
- Registry-driven alert fields and aliases.
- Numeric/text/boolean comparisons.
- Threshold crossing, range entry/exit, boolean transitions and value changes.
- Nested ALL/ANY/NOT condition trees.
- Configurable re-arm modes: ON_CROSSING, COOLDOWN, ONCE_PER_SYMBOL_DAY and MANUAL.
- SQLite rule/event/state persistence and deduplication.
- SDL flat-record → canonical alert-context adapter.
- Bounded point-in-time chart data.
- Isolated chart popup payload.
- Browser notification helper; alert detection remains server-side.

## Integration rule
The alert engine consumes authoritative decision/evidence fields. It must not duplicate or alter SDL qualification logic. The dashboard integration should call the adapter/engine only after desktop and replay regression tests pass.

## Streamlit Rule Builder

`alert_rule_builder.py` provides the isolated UI layer:

- field/operator/value condition builder
- nested `ALL` / `ANY` / `NOT` groups
- preset loading
- enable/priority/re-arm controls
- bounded alert-history table
- test against an explicitly supplied current snapshot
- persistence through `AlertStore`

The module does not start Streamlit, read SDL source files, or alter the Decision Centre. The production dashboard must explicitly call the UI only after integration regression testing.
