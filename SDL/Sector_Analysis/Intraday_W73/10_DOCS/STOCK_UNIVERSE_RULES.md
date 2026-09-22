# W73 Stock Universe Rules

The primary board is a filtered universe, not a raw log viewer.

Default V1 eligibility requires the configured source fields to be present:
Symbol, Close, ATM Straddle Price, ATM Straddle %, OI Chg, OI Chg %, Volume, IV, PCR Chg.

Optional thresholds are configuration values and default to unset; no undocumented threshold is silently invented.

Priority is descriptive and does not itself create a trading signal. `max_symbols` limits the primary board after eligibility.

Every decision carries `filter_version`, `evaluated_at`, and explicit exclusion reasons.
