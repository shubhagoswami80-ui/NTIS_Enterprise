# W73 Strategy V1

The maximum robust historical result is frozen at:

72.093%, n=129, 5 holdout dates, 45 symbols.

The maximum is tied by TWO candidate definitions. They remain separate W73-A and
W73-B variants. We do not choose one and we do not relax them into a broader rule.

Candidate IDs observed in the audit:

W73-A:
V8_PLUS_TRAJECTORY|orb_agree=NO|magnitude_count_band=0|px_all_negative_pre_maturity=True

W73-B:
V8_PLUS_TRAJECTORY|orb_price_agree=NO|magnitude_count_band=0|px_all_negative_pre_maturity=True

The exact full condition dictionaries remain authoritative in:
00_BASELINE\strategy_baseline_v1_tied_max.json

Next implementation gate:
build the W73-owned V8 feature engine that reproduces every required condition
from point-in-time raw intraday data. Do not import old analysis modules.
