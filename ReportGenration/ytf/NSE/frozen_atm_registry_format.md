# Frozen ATM registry format

Create one row per symbol and trading day:

```csv
trade_date,symbol,official_open_price,fixed_atm_strike,expiry,method
2026-09-14,ABB,7274,7300,29-Sep-2026,NSE_OFFICIAL_OPEN
```

`fixed_atm_strike` is authoritative for the entire session. The engine will not
recalculate it from the current/moving price.
