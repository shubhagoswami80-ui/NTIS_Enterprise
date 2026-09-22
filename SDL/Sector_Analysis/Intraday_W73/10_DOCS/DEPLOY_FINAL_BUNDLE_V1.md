# Final deployment

Destination:
`E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73`

This is a consolidated W73 source bundle. Copy its contents into the destination. Existing files with the same relative path are the final consolidated versions and may be replaced. Do not copy `.pytest_cache`/`__pycache__` (none are included).

Do not modify the external raw source root.

After deployment:
1. Run `python -m pytest 08_TESTS -q`.
2. Run `python 08_TESTS\w73_final_portal_freeze_gate.py`.
3. Start with `./11_DASHBOARD/start_w73_dashboard.ps1`.
4. Verify port 9005.

The source capability decision remains `EXACT_ORB_SOURCE_NOT_PROVEN`; this is intentionally fail-closed.
