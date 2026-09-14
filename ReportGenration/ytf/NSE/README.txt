# Frozen ATM Premium Skew Engine

This bundle is the next layer after hybrid source ingestion.

## Frozen rule

ATM is selected once from the official opening price and nearest available
strike. The selected strike is stored in a registry and remains fixed for the
whole session.

## Formula

`Bias % = ((ATM Call Premium - ATM Put Premium) / (ATM Call Premium + ATM Put Premium)) * 100`

## Included fields

- ATM CE/PE premium
- Premium Bias %
- ATM CE/PE IV
- ATM CE/PE volume
- ATM CE/PE OI
- ATM CE/PE change in OI
- official opening price
- fixed ATM strike

25-Delta IV is left blank because it requires genuine delta data or a separately
approved, validated delta source. It is not estimated from strike distance.

## Important input requirement

The chain file must contain paired `ce_ltp` and `pe_ltp` columns for each strike.
The registry must contain `symbol` and `fixed_atm_strike`.

## Example

```powershell
$py="E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"

& $py frozen_atm_premium_skew_engine.py `
  --chain "D:\path\paired_option_chain.csv" `
  --registry "D:\path\frozen_atm_registry.csv" `
  --output "D:\My-data\Share_P&L\ytdata\2026-09-14\premium_skew_snapshot.csv"
```

This engine does not calculate BROKE/BROKEN event states. That remains a separate
layer using the frozen thresholds:

- ±15%: BROKE (immediate)
- ±20%: BROKE (confirmed)
- ±30%: BROKEN status
