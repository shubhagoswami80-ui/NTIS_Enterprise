# NTIS SDL — Intraday W73 — Source of Truth

This folder is the complete source-of-truth boundary for W73.

Inside: all W73 application code, strategy logic, V8 feature definitions/adapters,
replay/historical logic, frozen baseline evidence, alerts, tests, configuration,
and W73-owned cache/output.

Outside at runtime: ONLY the existing live-data pipeline/source may be read,
through the explicit read-only live adapter boundary.

W73 must NOT import Python modules from the old SDL research folders,
Sector_Analysis research modules, .sector_intelligence, or old dashboards.

Development port: 9005.

Later integration entry point:
    from app import render_intraday_w73_page
    render_intraday_w73_page()

Historical/research code that W73 needs is copied into this folder and becomes
local source. Original locations are not runtime dependencies.
