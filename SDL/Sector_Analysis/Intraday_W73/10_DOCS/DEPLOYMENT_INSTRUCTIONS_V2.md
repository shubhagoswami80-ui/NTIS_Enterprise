# W73 Live Decision Integration v1 — Deployment

## Destination

`E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73`

## File actions

### NEW FILES
- `06_ALERTS\w73_live_decision_service.py`
- `07_OUTPUT\live_decision_contract_v2.json`
- `08_TESTS\test_w73_live_decision_service.py`
- `08_TESTS\test_w73_dashboard_integration.py`
- `10_DOCS\LIVE_DECISION_INTEGRATION_V1.md`
- `10_DOCS\DEPLOYMENT_INSTRUCTIONS_V2.md`
- `10_DOCS\copy_w73_live_decision_integration_v1.ps1`

### REPLACE EXISTING FILES
- `11_DASHBOARD\w73_dashboard.py`
- `11_DASHBOARD\start_w73_dashboard.ps1`

### DO NOT COPY
- `11_DASHBOARD\w73_dashboard_base.py` — bundle-internal reference only.

## Validation

From the W73 root, run:

`python -m pytest 08_TESTS -q`

Expected result after this bundle is installed: the prior 37 tests plus the new integration tests should pass. Do not start the dashboard if the suite is red.

## Start

`\.\11_DASHBOARD\start_w73_dashboard.ps1`

## Stop

`\.\11_DASHBOARD\stop_w73_dashboard.ps1`

## No production SDL changes

Do not copy any file into the existing SDL production dashboard tree outside W73.
