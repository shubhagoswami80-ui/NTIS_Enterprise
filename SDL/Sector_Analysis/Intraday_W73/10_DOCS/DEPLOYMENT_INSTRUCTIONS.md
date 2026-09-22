# Deployment — W73 Live Dashboard Data Foundation FINAL v1

## Destination
`E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73`

## Copy policy
This bundle is additive except:
- `11_DASHBOARD\w73_dashboard.py` = REPLACE EXISTING
- `11_DASHBOARD\start_w73_dashboard.ps1` = REPLACE EXISTING
- `11_DASHBOARD\stop_w73_dashboard.ps1` = REPLACE EXISTING

Do not modify `SDL\derivative_signal` or the existing SDL production dashboard.

## PowerShell
Run from the existing W73 PowerShell location; do not change directory.

1. Backup the three dashboard files if they already exist.
2. Copy bundle folders into the W73 root, preserving relative paths.
3. Ensure `.venv` is active.
4. Run:
`python -m pytest 08_TESTS -q`
5. Set source root if needed:
`$env:NTIS_W73_SOURCE_ROOT="D:\My-data\Share_P&L\Ichart Data\Screenshot"`
6. Start:
`.\11_DASHBOARD\start_w73_dashboard.ps1`
7. Open:
`http://localhost:9005`
8. Set Trading date to the required folder date and Source month to the correct month folder.
9. Verify `Data-as-of`, intervals, qualified stocks and source file/timestamp audit.
10. Stop:
`.\11_DASHBOARD\stop_w73_dashboard.ps1`

## First live validation
Use `2026-09-18` and `September26`.
Expected source folder:
`D:\My-data\Share_P&L\Ichart Data\Screenshot\September26\2026-09-18`

The exact source timestamp must be visible/auditable. Do not treat the filename's `29SEP26` report label as the trading date.

## If the safe PID launcher already exists
Replace it with this bundle's launcher. Do not use broad `Stop-Process python` commands.

## Phase-1 freeze
Do not begin replay/historical development until LIVE_DASHBOARD_FREEZE_GATE passes.
