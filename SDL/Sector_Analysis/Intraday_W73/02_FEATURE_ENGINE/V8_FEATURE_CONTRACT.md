# W73 V8 Feature Engine Contract

## Authoritative semantics

The preserved V8 `maturity_feature_matrix.csv` is the authoritative source for
exact V8 state semantics. This engine deliberately does not infer or recreate
those expressions from candidate CSV text.

The required V8 vocabulary is:

`orb_minutes, maturity, orb_dir, price_dir, fut_dir, option_dir, fut_state,
volume_state, ce_state, pe_state, pec_state, fut_oi_state, ce_pct_state,
pe_pct_state, pec_pct_state, fut_pct_state, price_state, orb_agree,
evidence_agreement, persistent, strength_bucket, core_count_band,
magnitude_count_band, orb_fut_agree, orb_price_agree`

## Frozen W73 variants

### W73-A
- `orb_agree = NO`
- `magnitude_count_band = 0`
- `px_all_negative_pre_maturity = True`

### W73-B
- `orb_price_agree = NO`
- `magnitude_count_band = 0`
- `px_all_negative_pre_maturity = True`

The variants are intentionally separate. They must not be merged into an
unvalidated OR rule.

## Missing-data rule

Missing is not zero. A missing required field never matches a W73 variant.

## Point-in-time rule

Trajectory observations at or after maturity are excluded. Future observations
must never influence a live feature snapshot.

## Current implementation boundary

This module is pure Python and has no Streamlit or legacy SDL imports. It can be
used by live, replay, and historical adapters without changing the production SDL
dashboard.
