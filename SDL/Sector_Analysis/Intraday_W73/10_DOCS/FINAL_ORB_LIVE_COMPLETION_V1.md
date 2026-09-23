# W73 Final ORB / Live Completion v1

This controlled completion promotes the confirmed Daywise source-family mapping:
the Daywise Price/OI workbook used by W73 is a FUTURES observation family, including
its Open/High/Low/Close and OI/Buildup fields.

Frozen causal ORB semantics:
- t0 = first available source timestamp for the symbol/day
- cutoff = t0 + 15 minutes
- ORB High = max High for rows timestamp <= cutoff
- ORB Low = min Low for rows timestamp <= cutoff
- breakout evidence is searched only on rows timestamp > cutoff
- no future observation is admitted to a maturity checkpoint

The deployment remains fail-closed for missing V8 inputs. W73-A and W73-B remain
unchanged.

Validation gate:
`python .\08_TESTS\w73_full_source_orb_gate.py September26 2026-09-18`

The gate is diagnostic and produces:
`07_OUTPUT\w73_full_source_orb_gate_v1.json`

This bundle does not modify the external raw source and does not modify the existing
SDL production dashboard.
