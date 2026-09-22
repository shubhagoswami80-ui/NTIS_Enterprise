# W73 Live Decision Module Recovery v1

The dashboard was correctly restored to the rich trader-board UI, but the consolidated deployment did not leave `06_ALERTS/w73_live_decision_service.py` in the installed W73 tree.

This bundle restores the authoritative live decision service from the previously validated integration bundle and adds the W73 `06_ALERTS` directory to the dashboard module search path.

No strategy logic is changed. No production SDL code is changed. No relaxed signal logic is introduced.
